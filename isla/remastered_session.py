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

    def cancel(self):
        if self.job is not None:
            self.job.close()
            self.job = None
            self.state = 'Research preparation canceled; active audio preserved.'
            self._stage = 'Canceled'
        self.requested = None

    def reset(self):
        self.cancel()
        self.applied = self.report = None
        self.state = 'Opt-in research preview — production modes remain available.'
        self._stage = 'Ready'
        self._published_buffer = None

    def prepare(self, mode, intensity):
        c = self.controller
        request = RenderRequest(mode, intensity)
        if c.source != 'file' or c.live.running or c.live.stream is not None:
            raise AudioError('Use an ALIVE local file and stop LIVE before preparing Remastered.')
        if not c.player.buffers or c.job is None or not c.job.done:
            raise AudioError('Load and finish preparing an ALIVE file first.')
        # Render the exact decoded source, never a processed buffer or a file
        # that might have changed since ALIVE loaded it.
        source = Path(c.job.directory.name, 'original.npy')
        self.cancel()
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
        if self.job is None:
            p = self.controller.player
            if self._stage == 'Applying' and (p.state != 'playing' or
                    (getattr(p, '_current', None) is self._published_buffer and
                     p._fade_pos >= len(p._fade))):
                self._stage = 'Completed'
                self.state = 'Validated Remastered buffer selected; transition handed to playback.'
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
            self.cancel()
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
