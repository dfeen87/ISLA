"""Bounded system capture -> worker DSP -> physical output monitoring.

One Core Audio duplex stream shares a callback clock; there are no independent
Python input/output clocks to drift apart. PortAudio owns device synchronization.
Python is not hard real-time: callbacks use only fixed copies, nonblocking ring
access, counters and timestamp arithmetic. FFTs run on the owned worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
import time

import numpy as np

from isla.playback import AudioError

BLOCK = 512
CAPACITY = 8
WARMUP_BLOCKS = 8


class BlockRing:
    """Preallocated bounded blocks. A callback never waits for the other thread."""
    def __init__(self, channels, capacity=CAPACITY):
        self.data = np.empty((capacity, BLOCK, channels), np.float32)
        self.stamps = np.zeros(capacity)
        self.capacity = capacity
        self.read = self.write = self.count = self.high_water = 0
        self.lock = threading.Lock()

    def push(self, data, stamp):
        if not self.lock.acquire(blocking=False):
            return False
        try:
            if self.count == self.capacity:
                return False
            self.data[self.write] = data
            self.stamps[self.write] = stamp
            self.write = (self.write + 1) % self.capacity
            self.count += 1
            self.high_water = max(self.high_water, self.count)
            return True
        finally:
            self.lock.release()

    def pop_into(self, target):
        if not self.lock.acquire(blocking=False):
            return None
        try:
            if not self.count:
                return None
            target[:] = self.data[self.read]
            stamp = self.stamps[self.read]
            self.read = (self.read + 1) % self.capacity
            self.count -= 1
            return stamp
        finally:
            self.lock.release()


@dataclass(frozen=True)
class LiveConfig:
    input_id: int
    output_id: int
    input_name: str
    output_name: str
    rate: int
    channels: int
    identity: tuple


class SystemCaptureBackend:
    def __init__(self, playback, routing=None):
        self.playback = playback
        self.routing = routing

    def configure(self, capture, output, rate):
        if rate not in (44100, 48000):
            raise AudioError("LIVE rate must be 44100 or 48000 Hz.")
        if not output:
            raise AudioError('Choose a physical output first: output "MacBook Pro Speakers"')
        if self.routing is None:
            from isla.coreaudio import CoreAudioRouting
            self.routing = CoreAudioRouting()
        source = self.playback.resolve_device(capture, "input")
        sink = self.playback.resolve_device(output, "output")
        if source["name"] != "BlackHole 2ch" or source["max_input_channels"] != 2:
            raise AudioError("LIVE capture requires standalone BlackHole 2ch. Install it separately; see README.")
        channels = min(2, sink["max_output_channels"])
        # Stereo capture cannot be silently downmixed into a mono output.
        if channels != 2:
            raise AudioError("BlackHole 2ch monitoring needs a stereo physical output.")
        identity = self.routing.validate(source["name"], sink["name"])
        try:
            sd = self.playback.sd
            sd.check_input_settings(device=source["index"], channels=2, dtype="float32", samplerate=rate)
            sd.check_output_settings(device=sink["index"], channels=2, dtype="float32", samplerate=rate)
        except Exception as exc:
            raise AudioError(f"Devices do not support stereo at {rate} Hz: {exc}") from exc
        return LiveConfig(source["index"], sink["index"], source["name"], sink["name"], rate, channels, identity)

    def validate(self, config):
        self.routing.validate(config.input_name, config.output_name, config.identity)

    def open(self, config, callback):
        stream = self.playback.sd.Stream(
            device=(config.input_id, config.output_id), samplerate=config.rate,
            channels=(config.channels, config.channels), dtype="float32",
            blocksize=BLOCK, latency="low", callback=callback,
        )
        try:
            # Verify actual native handles, not only PortAudio's cached names,
            # and recheck routing before the inactive stream can be started.
            self.routing.validate_stream(self.playback.sd, stream, config.identity)
            self.validate(config)
        except BaseException:
            stream.close()
            raise
        return stream


class LiveMonitor:
    def __init__(self, backend, processor_factory=None, monotonic_clock=None):
        self.backend = backend
        self.processor_factory = processor_factory
        # Inject a virtual device clock in manually pumped tests. Native LIVE
        # continues to use the real monotonic watchdog clock.
        self._monotonic_clock = monotonic_clock or time.monotonic
        self.stream = self.worker = None
        self.config = None
        self.mode = "bypass"
        self.state = "Stopped"
        self.error = ""
        self.halt = threading.Event()

    @property
    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def start(self, capture, output, rate=48000):
        if self.running:
            if self.halt.is_set():
                raise AudioError("LIVE is stopping; retry after monitor stop.")
            return "LIVE monitoring already active."
        self.stop()
        self.error = ""
        try:
            self.config = self.backend.configure(capture, output, rate)
            if self.processor_factory is None:
                from isla.streaming import StreamingDSP
                factory = StreamingDSP
            else:
                factory = self.processor_factory
            self.processor = factory(rate, self.config.channels)
            self.processor.select(self.mode)
            self.input = BlockRing(self.config.channels)
            self.output = BlockRing(self.config.channels)
            self.underflows = self.overflows = self.device_status = self.nonfinite = 0
            self.latency_ms = None
            self.max_worker_ms = 0.
            self.input_rms = self.output_rms = 0.
            self._empty_run = self._callbacks = 0
            self.halt.clear()
            self.stream = self.backend.open(self.config, self._callback)
            self.stream.start()
            self.state = "Running"
            self.worker = threading.Thread(target=self._work, name="isla-live", daemon=True)
            self.worker.start()
        except BaseException as exc:
            self.halt.set()
            self._release()
            self.state = "Failed"
            self.error = str(exc)
            if not isinstance(exc, Exception):
                raise
            raise AudioError(f"LIVE start failed: {exc}") from exc
        return "LIVE monitoring active."

    def select(self, mode):
        if mode not in ("bypass", "velvet", "legato", "melt"):
            raise ValueError("Choose velvet, legato, melt, or bypass.")
        self.mode = mode
        # Only the worker touches DSP state; it samples this reference each hop.

    def _fault(self, message):
        self.error = message
        self.halt.set()

    def _callback(self, indata, outdata, frames, timing, status):
        outdata.fill(0)
        if self.halt.is_set():
            return
        if frames != BLOCK:
            self._fault("Unexpected callback size; stopped safely. Retry monitoring.")
            return
        self._callbacks += 1
        if status:
            self.device_status += 1
        # Core Audio's duplex device can report an initial capture overflow while
        # its clocks settle. Discard the entire bounded startup interval before
        # feeding any DSP state, rather than hiding a discontinuity mid-session.
        if self._callbacks <= WARMUP_BLOCKS:
            return
        if status:
            if status.input_overflow or status.input_underflow:
                self._fault("Capture discontinuity reported by device "
                            f"(overflow={bool(status.input_overflow)}, underflow={bool(status.input_underflow)}); "
                            "stopped safely. Retry monitoring.")
                return
        if not self.input.push(indata, timing.inputBufferAdcTime):
            self.overflows += 1
            self._fault("Input buffer overflow/contention; stopped rather than accumulating delayed audio.")
            return
        stamp = self.output.pop_into(outdata)
        if stamp is None:
            self.underflows += 1
            self._empty_run += 1
            if self._empty_run >= CAPACITY:
                self._fault("Output starved; stopped safely. Close busy applications and retry.")
        else:
            self._empty_run = 0
            self.latency_ms = max(0., (timing.outputBufferDacTime - stamp) * 1000)

    def _work(self):
        block = np.empty((BLOCK, self.config.channels), np.float32)
        checked = self._monotonic_clock()
        callback_count = self._callbacks
        try:
            while not self.halt.is_set():
                now = self._monotonic_clock()
                if now - checked >= .25:
                    if not self.stream.active or self._callbacks == callback_count:
                        raise AudioError("Audio device disconnected or callbacks stopped. Reconnect and monitor start.")
                    self.backend.validate(self.config)
                    callback_count = self._callbacks
                    checked = now
                stamp = self.input.pop_into(block)
                if stamp is None:
                    self.halt.wait(.001)
                    continue
                started = time.perf_counter()
                if not np.isfinite(block).all():
                    self.nonfinite += 1
                    block.fill(0)
                self.input_rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
                self.processor.select(self.mode)
                result = self.processor.process_block(block)
                if result.shape != block.shape or not np.isfinite(result).all():
                    raise AudioError("DSP produced invalid audio; stopped safely.")
                self.output_rms = float(np.sqrt(np.mean(np.square(result, dtype=np.float64))))
                if not self.output.push(result, stamp - self.processor.delay / self.config.rate):
                    self.overflows += 1
                    raise AudioError("Output buffer overflow/contention; stopped safely.")
                self.max_worker_ms = max(self.max_worker_ms, (time.perf_counter() - started) * 1000)
        except Exception as exc:
            self._fault(str(exc))
        finally:
            self.halt.set()
            self._release()
            self.state = "Failed" if self.error else "Stopped"

    def _release(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.abort()
            except Exception as exc:
                self.error = self.error or f"Device abort reported: {exc}"
            finally:
                try:
                    stream.close()
                except Exception as exc:
                    self.error = self.error or f"Device close reported: {exc}"

    def stop(self):
        self.halt.set()
        if self.worker is not None:
            self.worker.join(timeout=3)
            if self.worker.is_alive():
                raise AudioError("Audio worker is still stopping; do not start another session.")
            self.worker = None
        self._release()
        self.state = "Failed" if self.error else "Stopped"
        return "LIVE monitoring stopped."

    def status(self):
        config = self.config
        latency = getattr(self, "latency_ms", None)
        return (f"Source: System Audio\nMode: {self.mode.title()}\nMonitor: {self.state}\n"
                f"Input: {config.input_name if config else 'Not opened'}\n"
                f"Output: {config.output_name if config else 'Not opened'}\n"
                f"Sample rate: {config.rate if config else 'Not opened'}\n"
                f"Latency (ADC/DAC estimate): {f'{latency:.1f} ms' if latency is not None else 'Pending audio'}\n"
                f"Signal RMS (input/output): {getattr(self, 'input_rms', 0):.5f} / {getattr(self, 'output_rms', 0):.5f}\n"
                f"Underflows: {getattr(self, 'underflows', 0)}; Overflows: {getattr(self, 'overflows', 0)}; "
                f"Device status: {getattr(self, 'device_status', 0)}; Muted non-finite blocks: {getattr(self, 'nonfinite', 0)}"
                + (f"\nError: {self.error}" if self.error else ""))
