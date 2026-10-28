"""Application LIVE transport with one producer and one consumer per audio ring.

Each thread publishes only its own sequence after copying a complete slot. A
slot remains owned by its consumer until that copy finishes. Capture never
waits for the DSP worker's copy mutex, and genuine queue-full conditions retain
LiveMonitor's original fail-closed path. Capacity and timestamp guards are shared
with the historical implementation; DSP and callback/worker logic are inherited.
"""
from __future__ import annotations

import sys
import threading

import numpy as np

from isla.live import BLOCK, CAPACITY, BlockRing, LiveMonitor
from isla.playback import AudioError


class SingleProducerConsumerRing:
    """Fixed storage; one producer and one consumer, with no shared copy lock.

    Input producer: PortAudio callback; input consumer: DSP worker.
    Output producer: DSP worker; output consumer: PortAudio callback.
    discard() is worker-only, during the monitor's gated recovery interval.
    """
    def __init__(self, channels, capacity=CAPACITY):
        self.capacity = capacity
        self.data = np.empty((capacity, BLOCK, channels), np.float32)
        self.stamps = np.zeros(capacity)
        self._produced = self._consumed = 0
        self.high_water = 0
        self.last_push_failure = 'none'

    @property
    def count(self):
        # Observational snapshots can straddle a publication; the owning
        # producer/consumer methods use their own stable sequence below.
        return max(0, self._produced - self._consumed)

    def push(self, data, stamp):
        produced = self._produced
        if produced - self._consumed >= self.capacity:
            self.last_push_failure = 'queue full'
            return False
        slot = produced % self.capacity
        np.copyto(self.data[slot], data)
        self.stamps[slot] = stamp
        self.high_water = max(self.high_water, produced + 1 - self._consumed)
        self._produced = produced + 1  # Publish only after the complete copy.
        return True

    def pop_into(self, target):
        consumed = self._consumed
        if consumed == self._produced:
            return None
        slot = consumed % self.capacity
        np.copyto(target, self.data[slot])
        stamp = self.stamps[slot]
        self._consumed = consumed + 1  # Release only after the complete copy.
        return stamp

    def discard(self):
        # Recovery gates the callback and rejects the worker's in-flight result
        # before reaching this method. No producer/consumer copy is in flight.
        count = self._produced - self._consumed
        self._consumed = self._produced
        return count


def _application_ring(channels):
    # Sequence publication relies on the standard CPython GIL. Keep the
    # historical synchronized ring on runtimes with different guarantees.
    if sys.implementation.name == 'cpython' and getattr(sys, '_is_gil_enabled', lambda: True)():
        return SingleProducerConsumerRing(channels)
    return BlockRing(channels)


class ReliableLiveMonitor(LiveMonitor):
    """Keep the reviewed lifecycle and guards, replacing only ring construction.

    The historical monitor has no ring-factory injection point. This startup
    adapter retains its worker-before-native-start handshake and cleanup path;
    callback, DSP work, recovery, stop and device validation are inherited.
    """
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
            self.input = _application_ring(self.config.channels)
            self.output = _application_ring(self.config.channels)
            self.halt.clear()
            self.stream = self.backend.open(self.config, self._callback)
            # PortAudio can invoke callbacks during stream.start(). Starting
            # the worker afterward leaves those capture blocks unprocessed and
            # may exhaust the fixed starvation limit before start() returns.
            self.worker = threading.Thread(target=self._work, name="isla-live", daemon=True)
            self.worker.start()
            self.stream.start()
            self._stream_started.set()
            if self.halt.is_set():
                # A callback may have failed synchronously during start().
                # Do not overwrite its fatal state with a false "Running".
                raise AudioError(self.error or "LIVE stopped during startup.")
            self.state = "Running"
        except BaseException as exc:
            self.halt.set()
            self._stream_started.set()
            # Once the worker is armed, it owns DSP access and may already be
            # inside a callback-driven block. Wait for it to release the stream
            # before declaring startup cleanup complete.
            if self.worker is not None:
                self.worker.join(timeout=3)
                if self.worker.is_alive():
                    self.state = "Failed"
                    self.error = self.error or str(exc)
                    self.last_interruption = self.error
                    self.recovery_state = "Stopped safely"
                    self.fatal_device_errors += 1
                    raise AudioError(
                        "LIVE startup failed; audio worker is still stopping. "
                        "Do not start another session."
                    ) from exc
                self.worker = None
            self._release()
            self.state = "Failed"
            self.error = self.error or str(exc)
            self.fatal_device_errors += int(not self.fatal_device_errors)
            self.last_interruption = self.error
            self.recovery_state = "Stopped safely"
            if not isinstance(exc, Exception):
                raise
            raise AudioError(f"LIVE start failed: {self.error}") from exc
        return "LIVE monitoring active."
