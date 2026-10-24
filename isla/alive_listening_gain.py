"""GUI-only ALIVE listening attenuation outside the byte-frozen playback engine.

The original BufferPlayer, mode crossfades and scientific source hashes remain
unchanged. This adapter attenuates only PCM sent to a GUI-owned output stream.
"""
from __future__ import annotations

import numpy as np

ALIVE_GUI_PLAY_LEVEL_PERCENT = 25


class AttenuatedALIVEBackend:
    """Delegate device handling while attenuating callback output only."""

    def __init__(self, backend, percent=ALIVE_GUI_PLAY_LEVEL_PERCENT):
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError('ALIVE output level must be an integer from 0 to 100%.')
        self.backend = backend
        self.output_level_percent = percent
        self.gain = percent / 100.0

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def open(self, samplerate, channels, callback, finished_callback):
        # Bind a constant gain when the stream opens. Never rely on the GUI
        # event loop to change a live callback's amplitude during playback.
        gain = self.gain

        def attenuated_callback(outdata, frames, timing, status):
            try:
                callback(outdata, frames, timing, status)
            finally:
                # Includes the final partially filled block when the frozen
                # BufferPlayer signals CallbackStop. No per-block allocations.
                np.multiply(outdata, gain, out=outdata)

        return self.backend.open(samplerate, channels, attenuated_callback,
                                 finished_callback)
