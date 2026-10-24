"""Bounded system capture -> worker DSP -> physical output monitoring.

One duplex callback exposes PortAudio timestamps. Separate native devices can
still have unequal clocks; PortAudio owns their buffering/synchronization.
Python is not hard real-time: callbacks use only fixed copies, nonblocking ring
access, counters and timestamp arithmetic. FFTs run on the owned worker thread.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import threading
import time

import numpy as np

from isla.playback import AudioError

BLOCK = 512
CAPACITY = 8
WARMUP_BLOCKS = 8
# Conservative operator-visible limits, not a claim about native glitch rates.
RECOVERY_QUIET_SECONDS = 10
MAX_RECOVERIES = 3
RECOVERY_BLOCKS = CAPACITY


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

    def discard(self):
        """Worker-only flush while the callback is gated to silence."""
        if not self.lock.acquire(blocking=False):
            raise AudioError("Recovery buffer contention; stopped safely.")
        try:
            count = self.count
            self.read = self.write = self.count = 0
            return count
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
        # Listening attenuation is local to ISLA's physical output. The
        # virtual BlackHole capture and macOS system volume are untouched.
        self.monitor_volume = 100
        self._applied_gain = 1.0
        self.state = "Stopped"
        self.error = ""
        self.halt = threading.Event()
        self._reset_session()

    def _reset_session(self):
        # Session totals survive stop/failure; an explicit new start resets them.
        self.underflows = self.overflows = self.device_status = self.nonfinite = 0
        self.input_overflows = self.input_underflows = 0
        self.output_underflows = self.output_overflows = 0
        self.ring_failures = self.capture_discontinuities = 0
        self.recovery_attempts = self.recoveries = self.failed_recoveries = 0
        self.fatal_device_errors = self.discarded_blocks = self.concealed_blocks = 0
        self.last_interruption = "None"
        self.recovery_state = "Clean"
        self._recovering = self._recovery_ready = False
        self._recovery_start = 0
        self._last_recovery = None
        self._last_adc = None
        self._empty_run = self._device_empty_run = self._callbacks = 0
        self.latency_ms = None
        self.max_worker_ms = self.max_routing_ms = self.max_queue_age_ms = 0.
        self.input_rms = self.output_rms = 0.

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
        self._reset_session()
        self.config = None
        try:
            self.config = self.backend.configure(capture, output, rate)
            if self.processor_factory is None:
                from isla.streaming import StreamingDSP
                factory = StreamingDSP
            else:
                factory = self.processor_factory
            self._factory = factory
            self.processor = factory(rate, self.config.channels)
            self.processor.select(self.mode)
            self._applied_gain = self.monitor_volume / 100.0
            self.input = BlockRing(self.config.channels)
            self.output = BlockRing(self.config.channels)
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
            self.fatal_device_errors += 1
            self.last_interruption = self.error
            self.recovery_state = "Stopped safely"
            if not isinstance(exc, Exception):
                raise
            raise AudioError(f"LIVE start failed: {exc}") from exc
        return "LIVE monitoring active."

    def select(self, mode):
        if mode not in ("bypass", "velvet", "legato", "melt"):
            raise ValueError("Choose velvet, legato, melt, or bypass.")
        self.mode = mode
        # Only the worker touches DSP state; it samples this reference each hop.

    def set_monitor_volume(self, percent):
        """Set bounded ISLA listening attenuation; 100% means exact unity."""
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            raise ValueError("LIVE listening volume must be an integer from 0 to 100%.")
        self.monitor_volume = percent

    def _apply_monitor_volume(self, result):
        """Worker-only, bounded 5 ms output ramp; DSP/recovery state is unchanged."""
        target = self.monitor_volume / 100.0
        previous = self._applied_gain
        if target != previous:
            frames = min(len(result), max(2, round(self.config.rate * .005)))
            ramp = np.linspace(previous, target, frames, dtype=np.float32)[:, None]
            np.multiply(result[:frames], ramp, out=result[:frames])
            if frames < len(result) and target != 1.0:
                result[frames:] *= target
            self._applied_gain = target
        elif target != 1.0:
            result *= target
        return result

    def _fault(self, message, device=False, ring=False):
        if self.halt.is_set():
            return
        self.error = message
        self.last_interruption = message
        self.fatal_device_errors += int(device)
        self.ring_failures += int(ring)
        if self._recovering:
            self.failed_recoveries += 1
        self.recovery_state = "Stopped safely"
        self.state = "Failed"
        self.halt.set()

    def _validate_devices(self):
        """Worker-only native inspection, also required before recovery commit."""
        started = time.perf_counter()
        try:
            if not self.stream.active:
                raise AudioError("Audio device disconnected. Reconnect and monitor start.")
            self.backend.validate(self.config)
            return True
        except Exception as exc:
            self._fault(str(exc), device=True)
            return False
        finally:
            self.max_routing_ms = max(self.max_routing_ms, (time.perf_counter() - started) * 1000)

    def _callback(self, indata, outdata, frames, timing, status):
        outdata.fill(0)
        if self.halt.is_set():
            return
        self._callbacks += 1
        if status:
            self.device_status += 1
        input_overflow = bool(getattr(status, "input_overflow", False))
        input_underflow = bool(getattr(status, "input_underflow", False))
        output_underflow = bool(getattr(status, "output_underflow", False))
        output_overflow = bool(getattr(status, "output_overflow", False))
        self.input_overflows += int(input_overflow)
        self.input_underflows += int(input_underflow)
        self.output_underflows += int(output_underflow)
        self.output_overflows += int(output_overflow)
        capture_gap = input_overflow or input_underflow
        if capture_gap:
            self.capture_discontinuities += 1
        if frames != BLOCK:
            self._fault("Unexpected callback size; stopped safely. Retry monitoring.", device=True)
            return
        # Core Audio's duplex device can report an initial capture overflow while
        # its clocks settle. Discard the entire bounded startup interval before
        # feeding any DSP state, rather than hiding a discontinuity mid-session.
        if self._callbacks <= WARMUP_BLOCKS:
            if capture_gap or output_underflow or output_overflow:
                self.last_interruption = "Device audio loss during discarded startup interval"
                self.recovery_state = "Startup loss reported"
            if capture_gap:
                self._last_recovery = self._callbacks
            return
        if output_overflow:
            self._fault("Device output overflow; stopped safely.", device=True)
            return
        self._device_empty_run = self._device_empty_run + 1 if output_underflow else 0
        if self._device_empty_run >= CAPACITY:
            self._fault("Persistent device output underflow; stopped safely.", device=True)
            return
        if capture_gap:
            self.last_interruption = ("Capture input overflow; audio lost" if input_overflow
                                      else "Capture input underflow; audio lost")
            if (self._recovering or self.recovery_attempts >= MAX_RECOVERIES or
                    (self._last_recovery is not None and
                     (self._callbacks - self._last_recovery) * BLOCK / self.config.rate < RECOVERY_QUIET_SECONDS)):
                self.failed_recoveries += int(not self._recovering)
                self._fault("Repeated capture discontinuity; recovery limit reached; stopped safely.", device=True)
                return
            self.recovery_attempts += 1
            self._last_recovery = self._recovery_start = self._callbacks
            self._recovery_ready = False
            self._recovering = True  # Publish last: worker owns flush + DSP reset.
            self.recovery_state = "Recovering (audio lost)"
            self.state = "Recovering"
            self.latency_ms = None
            self.input_rms = self.output_rms = 0.
            self._last_adc = None
            self.concealed_blocks += 1
            return
        if self._recovering:
            if self._callbacks - self._recovery_start >= RECOVERY_BLOCKS:
                self._fault("Capture recovery deadline exceeded; stopped safely.")
                return
            if not self._recovery_ready:
                self.concealed_blocks += 1
                return
        adc, dac = timing.inputBufferAdcTime, timing.outputBufferDacTime
        if not math.isfinite(adc) or not math.isfinite(dac) or (self._last_adc is not None and adc <= self._last_adc):
            self._fault("Invalid or regressing device timestamps; stopped safely.", device=True)
            return
        self._last_adc = adc
        if not self.input.push(indata, adc):
            self.overflows += 1
            self._fault("Input buffer overflow/contention; stopped rather than accumulating delayed audio.", ring=True)
            return
        stamp = self.output.pop_into(outdata)
        if stamp is None:
            self.underflows += 1
            self._empty_run += 1
            if self._recovering:
                self.concealed_blocks += 1
            if self._empty_run >= CAPACITY:
                self._fault("Output starved; stopped safely. Close busy applications and retry.", ring=True)
        else:
            age = adc - (stamp + self.processor.delay / self.config.rate)
            self.max_queue_age_ms = max(self.max_queue_age_ms, age * 1000)
            if age > CAPACITY * BLOCK / self.config.rate + 1e-6 or age < -1e-6:
                outdata.fill(0)
                self._fault("Stale or invalid output timestamp; stopped without replay.", device=True)
                return
            self._empty_run = 0
            self.latency_ms = max(0., (dac - stamp) * 1000)
            if self._recovering:
                self.recoveries += 1
                self._recovering = False
                self.recovery_state = "Recovered (audio lost)"
                self.state = "Running"
        if output_underflow:
            self.last_interruption = "Device output underflow; audio lost"
            if not self._recovering:
                self.recovery_state = "Device loss reported"

    def _work(self):
        block = np.empty((BLOCK, self.config.channels), np.float32)
        checked = self._monotonic_clock()
        callback_count = self._callbacks
        try:
            while not self.halt.is_set():
                now = self._monotonic_clock()
                if now - checked >= .25:
                    if not self.stream.active or self._callbacks == callback_count:
                        self._fault("Audio device disconnected or callbacks stopped. Reconnect and monitor start.", device=True)
                        break
                    if not self._validate_devices():
                        break
                    callback_count = self._callbacks
                    checked = now
                if self._recovering and not self._recovery_ready:
                    if not self._validate_devices():
                        break
                    if self.halt.is_set():
                        break
                    # The callback neither reads nor writes rings until ready.
                    # This worker has finished any in-flight old DSP result.
                    try:
                        self.discarded_blocks += self.input.discard()
                        self.discarded_blocks += self.output.discard()
                    except AudioError as exc:
                        self._fault(str(exc), ring=True)
                        break
                    self.processor = self._factory(self.config.rate, self.config.channels)
                    self.processor.select(self.mode)
                    self._empty_run = 0
                    self._recovery_ready = True
                stamp = self.input.pop_into(block)
                if stamp is None:
                    self.halt.wait(.001)
                    continue
                started = time.perf_counter()
                latest_adc = self._last_adc
                age = latest_adc - stamp if latest_adc is not None else 0.
                self.max_queue_age_ms = max(self.max_queue_age_ms, age * 1000)
                if age > CAPACITY * BLOCK / self.config.rate + 1e-6 or age < -1e-6:
                    self._fault("Stale or invalid input timestamp; stopped without replay.", device=True)
                    break
                if not np.isfinite(block).all():
                    self.nonfinite += 1
                    block.fill(0)
                self.input_rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
                self.processor.select(self.mode)
                result = self.processor.process_block(block)
                if self.halt.is_set() or (self._recovering and not self._recovery_ready):
                    self.discarded_blocks += 1
                    continue
                if result.shape != block.shape or not np.isfinite(result).all():
                    raise AudioError("DSP produced invalid audio; stopped safely.")
                self._apply_monitor_volume(result)
                self.output_rms = float(np.sqrt(np.mean(np.square(result, dtype=np.float64))))
                if not self.output.push(result, stamp - self.processor.delay / self.config.rate):
                    self.overflows += 1
                    self._fault("Output buffer overflow/contention; stopped safely.", ring=True)
                    break
                self.max_worker_ms = max(self.max_worker_ms, (time.perf_counter() - started) * 1000)
        except Exception as exc:
            self._fault(str(exc))
        finally:
            self.halt.set()
            self._release()
            self.state = "Failed" if self.error else "Stopped"
            if self._recovering and not self.error:
                self.recovery_state = "Stopped during recovery"

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
                f"ISLA listening volume: {self.monitor_volume}% (physical output only)\n"
                f"Latency (ADC/DAC estimate): {f'{latency:.1f} ms' if latency is not None else 'Pending audio'}\n"
                f"Signal RMS (input/output): {getattr(self, 'input_rms', 0):.5f} / {getattr(self, 'output_rms', 0):.5f}\n"
                f"Underflows: {getattr(self, 'underflows', 0)}; Overflows: {getattr(self, 'overflows', 0)}; "
                f"Device status: {getattr(self, 'device_status', 0)}; Muted non-finite blocks: {getattr(self, 'nonfinite', 0)}"
                f"\nDevice input overflow/underflow events: {self.input_overflows} / {self.input_underflows}"
                f"\nDevice output underflow/overflow events: {self.output_underflows} / {self.output_overflows}"
                f"\nApplication ring failures: {self.ring_failures}; Output ring empty/contention events: {self.underflows}"
                f"\nCapture discontinuities (including startup): {self.capture_discontinuities}"
                f"\nRecovery attempts/completed/failed: {self.recovery_attempts} / {self.recoveries} / {self.failed_recoveries}"
                f"\nFatal device errors: {self.fatal_device_errors}; Discarded queued/in-flight blocks: {self.discarded_blocks}"
                f"\nRecovery silence blocks: {self.concealed_blocks}; Recovery state: {self.recovery_state}"
                f"\nLast interruption: {self.last_interruption}"
                f"\nMax routing check/worker/queue age ms: {self.max_routing_ms:.2f} / {self.max_worker_ms:.2f} / {self.max_queue_age_ms:.2f}"
                + (f"\nError: {self.error}" if self.error else ""))
