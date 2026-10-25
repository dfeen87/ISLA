"""GUI-only ALIVE listening attenuation outside the byte-frozen playback engine.

The original BufferPlayer, mode crossfades and scientific source hashes remain
unchanged. This adapter attenuates only PCM sent to a GUI-owned output stream.
"""
from __future__ import annotations

from isla.listening_gain import GainRamp

ALIVE_GUI_PLAY_LEVEL_PERCENT = 25


class AttenuatedALIVEBackend:
    """Delegate device handling while attenuating callback output only."""

    def __init__(self, backend, percent=ALIVE_GUI_PLAY_LEVEL_PERCENT):
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError('ALIVE output level must be an integer from 0 to 100%.')
        self.backend = backend
        self.output_level_percent = percent
        self._ramp = None
        self.callbacks = self.status_events = self.underflows = self.dac_gaps = 0

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def set_percent(self, percent):
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError('ALIVE output level must be an integer from 0 to 100%.')
        self.output_level_percent = percent

    @property
    def applied_percent(self):
        return self._ramp.applied * 100 if self._ramp is not None else None

    def open(self, samplerate, channels, callback, finished_callback):
        ramp = GainRamp(samplerate, self.output_level_percent)
        self._ramp = ramp
        self.callbacks = self.status_events = self.underflows = self.dac_gaps = 0
        expected_dac = None

        def attenuated_callback(outdata, frames, timing, status):
            nonlocal expected_dac
            # Bounded scalar bookkeeping only; no logging, arrays, locks or
            # waveform analysis in the callback. Totals survive stop/cleanup.
            self.callbacks += 1
            if status:
                self.status_events += 1
                self.underflows += int(bool(getattr(status, 'output_underflow', False)))
            dac = timing.outputBufferDacTime
            if expected_dac is not None and abs(dac - expected_dac) > 2 / samplerate:
                self.dac_gaps += 1
            expected_dac = dac + frames / samplerate
            try:
                callback(outdata, frames, timing, status)
            finally:
                # Includes the final partially filled block when the frozen
                # BufferPlayer signals CallbackStop. No per-block allocations.
                ramp.apply(outdata, self.output_level_percent)

        return self.backend.open(samplerate, channels, attenuated_callback,
                                 finished_callback)

    def diagnostics(self):
        return (f'callbacks={self.callbacks}; status events={self.status_events}; '
                f'underflows={self.underflows}; DAC gaps={self.dac_gaps} '
                '(timestamp deviation >2 samples; not an acoustic measurement)')
