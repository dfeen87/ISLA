"""ALIVE GUI-only vinyl slowdown: half tempo and half pitch at the native output rate.

A bounded 2x linear interpolator sits outside the frozen BufferPlayer/DSP.
Source buffers, their sample cursor, export PCM, and terminal-only audio stay
unchanged. Speed changes are committed only with the stream stopped.
"""
from __future__ import annotations

import numpy as np


class _SlowStream:
    """Expose a half-rate DAC clock to BufferPlayer's existing cursor logic."""
    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)

    @property
    def time(self):
        return self._stream.time * 0.5


class VinylSpeedBackend:
    """At 50%, interpolate each source frame into two output frames.

    Opens the hardware at the original sample rate; no unsupported 22.05/24 kHz
    hardware mode, callback file I/O, FFT, or extra player is involved.
    """
    def __init__(self, backend):
        self.backend = backend
        self.slowdown = False

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def open(self, samplerate, channels, callback, finished_callback):
        if not self.slowdown:
            return self.backend.open(samplerate, channels, callback, finished_callback)

        # Allocate outside the PortAudio callback, including the timing proxy.
        scratch = np.empty((4096, channels), np.float32)
        previous = np.zeros((channels,), np.float32)
        timing_proxy = type('Timing', (), {'outputBufferDacTime': 0.0})()
        has_previous = False
        second_pending = False
        source_ended = False

        def slower_callback(outdata, frames, timing, status):
            nonlocal has_previous, second_pending, source_ended
            outdata.fill(0)
            timing_proxy.outputBufferDacTime = timing.outputBufferDacTime * 0.5
            cursor = 0
            if second_pending and frames:
                outdata[0] = previous
                second_pending = False
                cursor = 1
            if source_ended:
                # An odd final output packet can leave the second half of the
                # final source frame pending. Deliver it before stopping.
                if not second_pending:
                    raise self.backend.CallbackStop
                return

            while cursor < frames:
                # Bound scratch size independently of the device's callback size.
                count = min(frames - cursor, len(scratch) * 2)
                needed = (count + 1) // 2
                ended = False
                try:
                    callback(scratch[:needed], needed, timing_proxy, status)
                except self.backend.CallbackStop:
                    # The final callback carries valid PCM plus zero padding.
                    ended = True
                block = outdata[cursor:cursor + count]
                even = block[::2]
                even[:] = scratch[:needed]
                block[1::2] = scratch[:count // 2]
                # Causal linear interpolation: halfway from previous source
                # sample to current; the odd output sample is current.
                if has_previous:
                    np.add(even[0], previous, out=even[0])
                    even[0] *= 0.5
                if needed > 1:
                    np.add(even[1:], scratch[:needed - 1], out=even[1:])
                    even[1:] *= 0.5
                np.copyto(previous, scratch[needed - 1])
                has_previous = True
                second_pending = bool(count % 2)
                cursor += count
                if ended:
                    if second_pending:
                        source_ended = True
                        return
                    raise self.backend.CallbackStop

        stream = self.backend.open(samplerate, channels, slower_callback, finished_callback)
        return _SlowStream(stream)
