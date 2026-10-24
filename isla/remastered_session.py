"""Research buffer publication on the existing serialized command worker."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from isla.playback import AudioError
from isla.remastered import RenderRequest
from isla.remastered_preparation import RemasteredPreparation


class RemasteredSession:
    def __init__(self, controller, factory=RemasteredPreparation):
        self.controller = controller
        self.factory = factory
        self.job = None
        self.requested = self.applied = None
        self.report = None
        self.state = 'Opt-in research preview — production modes remain available.'

    def cancel(self):
        if self.job is not None:
            self.job.close()
            self.job = None
            self.state = 'Research preparation canceled; active audio preserved.'
        self.requested = None

    def reset(self):
        self.cancel()
        self.applied = self.report = None
        self.state = 'Opt-in research preview — production modes remain available.'

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
        self.job = self.factory(source, c.player.sr, request)
        self.requested = request
        self.state = self.job.state
        return self.state

    def poll(self):
        if self.job is None:
            return
        try:
            result = self.job.poll()
            self.state = self.job.state
            if result is None:
                return
            buffer, report = result
            p = self.controller.player
            if (buffer.dtype != np.float32 or buffer.shape != p.buffers['original'].shape
                    or not np.isfinite(buffer).all() or not report['numerical_pass']):
                raise ValueError('Invalid prepared research buffer; active audio preserved.')
            request = self.requested
            key = 'remastered_' + request.mode
            # Publish the new reference using BufferPlayer's existing 5 ms
            # crossfade and cursor. Never call install/stop or add callback DSP.
            p.buffers = {name: value for name, value in p.buffers.items()
                         if not name.startswith('remastered_')}
            p.buffers[key] = buffer
            p.select(key)
            self.applied, self.report = request, report
            self.state = f'Remastered {request.mode.title()} — {request.intensity}% ready'
        except Exception as exc:
            self.state = str(exc)
            self.cancel()
            self.state = str(exc)
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
