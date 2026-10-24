"""Prepared-buffer playback through PortAudio; no DSP runs in the callback."""
from __future__ import annotations

import numpy as np


class AudioError(RuntimeError):
    """An actionable audio output error for the terminal."""


class SoundDeviceBackend:
    def __init__(self):
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise AudioError("Playback unavailable. Install: python -m pip install -e '.[playback]'") from exc
        self.sd = sd
        self.CallbackStop = sd.CallbackStop

    def output_name(self):
        try:
            return self.sd.query_devices(kind="output")["name"]
        except Exception as exc:
            raise AudioError("No output device. Select speakers/headphones in macOS System Settings > Sound.") from exc

    def open(self, samplerate, channels, callback, finished_callback):
        try:
            self.sd.check_output_settings(samplerate=samplerate, channels=channels, dtype="float32")
            return self.sd.OutputStream(
                samplerate=samplerate, channels=channels, dtype="float32",
                blocksize=512, callback=callback, finished_callback=finished_callback,
            )
        except Exception as exc:
            raise AudioError(f"Cannot open output at {samplerate} Hz / {channels} channel(s): {exc}") from exc


class BufferPlayer:
    """One owned stream, an immutable buffer selection, and a shared sample cursor.

    Only the callback advances the cursor while playing. Commands abort the stream
    before changing it. Mode changes publish a reference, consumed at a block edge.
    """
    def __init__(self, backend):
        self.backend = backend
        self.stream = None
        self.buffers = {}
        self.sr = 0
        self.cursor = 0
        self.mode = "original"
        self.state = "idle"
        self.warning = ""
        self.output = "Not opened"
        self._ended = False
        self._origin = None
        self._base = 0

    def install(self, buffers, sr):
        self.stop()
        self.buffers = buffers
        self.sr = sr
        self.mode = "original"
        self._selected = buffers["original"]
        self.state = "stopped"
        # Preallocate a short transition and scratch space outside the callback.
        self._fade = np.linspace(0, 1, max(2, round(sr * .005)), dtype=np.float32)[:, None]
        self._inverse = 1 - self._fade
        self._scratch = np.empty((512, self._selected.shape[1]), dtype=np.float32)

    def select(self, mode):
        if mode not in self.buffers:
            raise AudioError("Load an audio file before selecting a mode.")
        self.mode = mode
        self._selected = self.buffers[mode]

    def _callback(self, outdata, frames, timing, status):
        outdata.fill(0)
        if status:
            self.warning = "Audio output underrun/status reported; try closing other busy applications."
        if self._origin is None:
            self._origin = timing.outputBufferDacTime
        start = self.cursor
        selected = self._selected
        count = min(frames, len(selected) - start)
        if selected is not self._current:
            self._previous = self._current
            self._current = selected
            self._fade_pos = 0
        if count:
            outdata[:count] = selected[start:start + count]
            n = min(count, len(self._fade) - self._fade_pos, len(self._scratch))
            if n > 0:
                a, b = self._fade_pos, self._fade_pos + n
                np.multiply(outdata[:n], self._fade[a:b], out=outdata[:n])
                np.multiply(self._previous[start:start + n], self._inverse[a:b], out=self._scratch[:n])
                np.add(outdata[:n], self._scratch[:n], out=outdata[:n])
                self._fade_pos = b
            self.cursor = start + count
        if self.cursor >= len(selected):
            raise self.backend.CallbackStop

    def _finished(self):
        # PortAudio owns this thread. Stream cleanup stays on the command thread.
        self._ended = True

    def refresh(self):
        if self.state == "playing" and self._ended:
            self._close_stream()
            self.state = "completed"
        elif self.state == "playing" and self.stream is not None:
            try:
                active = self.stream.active
            except Exception:
                active = False
            if not active:
                self._close_stream()
                self.state = "paused"
                self.warning = "Audio stream stopped unexpectedly. Check the output device, then play again."

    @property
    def position(self):
        if self.stream is not None and self._origin is not None:
            # Cursor includes queued output. Use the DAC clock for pause/status.
            try:
                now = self.stream.time
            except Exception:
                return self.cursor
            return max(self._base, min(self.cursor, self._base + round(
                max(0, now - self._origin) * self.sr)))
        return self.cursor

    def play(self):
        self.refresh()
        if not self.buffers:
            raise AudioError("Load an audio file first.")
        if self.state == "playing":
            return "Already playing."
        resumed = self.state == "paused"
        if self.cursor >= len(self._selected):
            self.cursor = 0
        self._base = self.cursor
        self._origin = None
        self._ended = False
        self.warning = ""
        self._current = self._selected
        self._previous = self._selected
        self._fade_pos = len(self._fade)
        try:
            self.output = self.backend.output_name()
            self.stream = self.backend.open(self.sr, self._selected.shape[1], self._callback, self._finished)
            self.state = "playing"
            self.stream.start()
        except Exception as exc:
            self._close_stream()
            self.state = "paused" if resumed else "stopped"
            raise AudioError(f"Playback failed: {exc}") from exc
        return "Playback resumed." if resumed else f"Playing {self.mode} audio."

    def _close_stream(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.abort()
            except Exception as exc:
                self.warning = f"Output device stopped responding: {exc}"
            finally:
                try:
                    stream.close()
                except Exception as exc:
                    self.warning = f"Output device cleanup reported: {exc}"

    def pause(self):
        self.refresh()
        if self.state != "playing":
            return "Playback is not playing."
        position = self.position
        self._close_stream()
        self.cursor = position
        self.state = "paused"
        return "Playback paused."

    def stop(self):
        self._close_stream()
        self.cursor = 0
        self.state = "stopped" if self.buffers else "idle"

    def close(self):
        self.stop()
        self.buffers = {}
        # Release mapped buffer references before the preparation directory goes.
        self._selected = self._current = self._previous = None
        self.state = "idle"
