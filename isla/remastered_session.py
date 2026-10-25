"""Research buffer publication on the existing serialized command worker."""
from __future__ import annotations

from pathlib import Path
import hashlib

import numpy as np

from isla.playback import AudioError
from isla.remastered import CORE_SHA256, RenderRequest, output_metrics
from isla.remastered_preparation import MAX_SECONDS, RemasteredPreparation


class RemasteredSession:
    def __init__(self, controller, factory=RemasteredPreparation):
        self.controller = controller
        self.factory = factory
        self.job = None
        self.requested = self.applied = None
        self.report = None
        self.state = 'Opt-in research preview — production modes remain available.'
        self._stage = 'Ready'
        self._published_buffer = None
        self.workspace = False
        self.previous_mode = None
        self._source = None

    @property
    def stage(self):
        if self.job is not None:
            return getattr(self.job, 'stage', 'Preparing')
        if self._stage == 'Ready':
            c, p = self.controller, self.controller.player
            if (c.source != 'file' or c.live.running or c.live.stream is not None or
                    not p.buffers or p.sr not in (44100,48000) or
                    p.buffers['original'].shape[1] not in (1,2) or
                    not 0 < len(p.buffers['original']) <= p.sr * MAX_SECONDS):
                return 'Unavailable'
        return self._stage

    def _close_job(self):
        if self.job is not None:
            self.job.close()
            self.job = None
        self.requested = None

    def _same_source(self):
        return (not self.controller.closed and self.controller.source == 'file' and
                self.controller.player.buffers.get('original') is self._source)

    def admit(self):
        c, p = self.controller, self.controller.player
        if c.source != 'file' or c.live.running or c.live.stream is not None:
            raise AudioError('Use an ALIVE local file and stop LIVE before entering Remastered.')
        if not p.buffers or c.job is None or not c.job.done:
            raise AudioError('Load and finish preparing an ALIVE file first.')
        original = p.buffers['original']
        if p.sr not in (44100, 48000):
            raise AudioError('Remastered ALIVE requires a 44.1/48 kHz source.')
        if original.ndim != 2 or original.shape[1] not in (1, 2):
            raise AudioError('Remastered ALIVE requires mono or stereo audio.')
        if not 0 < len(original) <= p.sr * MAX_SECONDS:
            raise AudioError('Remastered ALIVE requires a non-empty excerpt of at most 30 seconds.')

    def enter(self):
        self.admit()  # All admission checks precede any playback change.
        if self.workspace:
            if self._same_source():
                return self.state
            self.reset()
        p = self.controller.player
        if p.mode not in ('original', 'velvet', 'legato', 'melt'):
            raise AudioError('Return to a traditional mode before entering Remastered.')
        self.previous_mode, self._source = p.mode, p.buffers['original']
        p.select('original')  # Existing block-edge crossfade; cursor/stream untouched.
        self.workspace = True
        self._stage = 'Entered'
        self.state = 'Remastered workspace entered; Original / Bypass selected.'
        return self.state

    def cancel(self):
        self._close_job()  # Cancellation wins even over a completed, unpolled result.
        self._restore('Canceled')

    def return_previous(self):
        if self.job is not None:
            raise AudioError('Cancel Preparation before returning to the previous mode.')
        self._restore('Returning')

    def _restore(self, stage):
        p = self.controller.player
        if self.workspace and self._same_source() and self.previous_mode in p.buffers:
            p.select(self.previous_mode)
            self._published_buffer = p._selected
            self._stage = stage
            self.state = ('Preparation canceled; ' if stage == 'Canceled' else '') + \
                f'Returning to previous mode: {self.previous_mode.title()}.'
        else:
            self._stage = 'Canceled'
            self.state = 'Workspace closed; no previous recording restored.'
        self.workspace = False
        self.previous_mode = self._source = None

    def reset(self):
        self._close_job()
        self.applied = self.report = None
        self.state = 'Opt-in research preview — production modes remain available.'
        self._stage = 'Ready'
        self._published_buffer = None
        self.workspace = False
        self.previous_mode = self._source = None

    def prepare(self, mode, intensity):
        c = self.controller
        request = RenderRequest(mode, intensity)
        self.admit()
        if not self.workspace or not self._same_source():
            raise AudioError('Enter Remastered before preparing a research mode.')
        source = Path(c.job.directory.name, 'original.npy')
        self._close_job()
        try:
            self.job = self.factory(source, c.player.sr, request)
        except Exception as exc:
            self._stage, self.state = 'Failed', str(exc)
            raise
        self.requested = request
        self.state = self.job.state
        self._stage = 'Preparing'
        return self.state

    def poll(self):
        if self.workspace and not self._same_source():
            self.reset()
            return
        if self.job is None:
            p = self.controller.player
            if self._stage in ('Applying', 'Returning') and (p.state != 'playing' or
                    (getattr(p, '_current', None) is self._published_buffer and
                     p._fade_pos >= len(p._fade))):
                returning = self._stage == 'Returning'
                self._stage = 'Returned' if returning else 'Completed'
                self.state = ('Previous traditional mode restored.' if returning else
                              'Validated Remastered buffer selected; transition handed to playback.')
            return
        try:
            result = self.job.poll()
            self.state = self.job.state
            if result is None:
                return
            buffer, report = result
            p = self.controller.player
            if (buffer.dtype != np.float32 or buffer.shape != p.buffers['original'].shape
                    or not np.isfinite(buffer).all()):
                raise ValueError('Invalid prepared research buffer; active audio preserved.')
            request = self.requested
            # Validate metadata and actual PCM BEFORE changing any player
            # reference. A malformed/lying child result must leave audio intact.
            original = p.buffers['original']
            try:
                consistent = (report['schema'] == 1 and report['mode'] == request.mode and
                    report['intensity_percent'] == request.intensity and
                    report['requested_depth'] == request.depth and
                    report['research_core_sha256'] == CORE_SHA256 and
                    report['source_audio_sha256'] == hashlib.sha256(original.tobytes()).hexdigest() and
                    report['sample_rate'] == p.sr and report['channels'] == original.shape[1] and
                    report['samples'] == len(original) and report['numerical_pass'] is True and
                    bool(report['checks']) and all(v is True for v in report['checks'].values()) and
                    0 <= report['applied_depth_active_mean'] <= report['applied_depth_max'] <= request.depth and
                    0 <= report['vetoed_frames'] <= report['frame_count'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError('Malformed Remastered validation report; active audio preserved.') from exc
            if not consistent:
                raise ValueError('Inconsistent Remastered validation report; active audio preserved.')
            measured = output_metrics(original, buffer)
            if not all(measured[k] for k in ('finite', 'shape_preserved', 'peak_screen_pass')):
                raise ValueError('Prepared PCM failed output peak validation; active audio preserved.')
            if request.intensity == 0 and not np.array_equal(original, buffer):
                raise ValueError('Zero-depth PCM differs from original; active audio preserved.')
            report = dict(report, playback_output=measured)
            self._stage = 'Validated'
            key = 'remastered_' + request.mode
            # Publish the new reference using BufferPlayer's existing 5 ms
            # crossfade and cursor. Never call install/stop or add callback DSP.
            p.buffers = {name: value for name, value in p.buffers.items()
                         if not name.startswith('remastered_')}
            p.buffers[key] = buffer
            p.select(key)
            self._published_buffer = buffer
            self._stage = 'Applying' if p.state == 'playing' else 'Completed'
            self.applied, self.report = request, report
            self.state = f'Remastered {request.mode.title()} — {request.intensity}% ready'
        except Exception as exc:
            self.state = str(exc)
            self._close_job()
            self.state = str(exc)
            self._stage = 'Failed'
            raise
        else:
            self.job.close()
            self.job = None
            self.requested = None

    @property
    def summary(self):
        if self.report is None:
            return ''
        r = self.report
        return (f"Requested depth {r['requested_depth']:.4f}; applied mean "
                f"{r['applied_depth_active_mean']:.4f}, max {r['applied_depth_max']:.4f}; "
                f"vetoed {r['vetoed_frames']}/{r['frame_count']} frames; "
                f"peak {r['playback_output']['sample_peak']:.5f}; "
                f"RMS {r['playback_output']['rms']:.5f}; numerical screens PASS.")
