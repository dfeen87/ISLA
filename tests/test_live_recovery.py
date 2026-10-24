"""Deterministic transport loss/races. No native hardware acceptance implied."""
from contextlib import contextmanager
from types import SimpleNamespace
import threading

import numpy as np
import pytest

from isla.live import (BLOCK, CAPACITY, MAX_RECOVERIES, RECOVERY_BLOCKS,
                       RECOVERY_QUIET_SECONDS, LiveMonitor)
from isla.streaming import MODES, StreamingDSP
from test_live import FakeBackend, PassThrough, wait_for, warmup

ZERO = np.zeros((BLOCK, 2), np.float32)
GAP = SimpleNamespace(input_overflow=True)


def flags(**values):
    return SimpleNamespace(**values)


@contextmanager
def session(factory=StreamingDSP, rate=48000):
    backend = FakeBackend()
    gate = threading.Event()
    gate.set()
    class Scheduled(factory):
        def process_block(self, block):
            assert gate.wait(2)
            return super().process_block(block)
    monitor = LiveMonitor(backend, Scheduled,
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.)
    monitor._test_process_gate = gate
    monitor.start("BlackHole 2ch", "Test speakers", rate)
    warmup(monitor)
    try:
        yield monitor, backend.streams[-1]
    finally:
        monitor.stop()
    assert all(stream.closed for stream in backend.streams)


def pump(monitor, stream, block=ZERO, status=None):
    # Explicitly schedule DSP after the manually pumped callback returns. This
    # models the normal one-hop pipeline without accidental host-thread races;
    # contention and in-flight interleavings have separate forced tests below.
    monitor._test_process_gate.clear()
    try:
        result = stream.pump(block, status)
    finally:
        monitor._test_process_gate.set()
    wait_for(lambda: monitor.output.count == 1 or monitor.halt.is_set())
    assert not monitor.halt.is_set(), monitor.error
    return result


def recover(monitor, stream, status=GAP):
    assert not stream.pump(np.full_like(ZERO, .95), status).any()
    assert monitor.state == "Recovering" and not monitor.halt.is_set()
    wait_for(lambda: monitor._recovery_ready or monitor.halt.is_set())
    assert not monitor.halt.is_set(), monitor.error


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("mode", MODES)
def test_isolated_gap_discards_history_matches_fresh_dsp_and_finite_peak(mode, rate):
    with session(rate=rate) as (monitor, stream):
        monitor.select(mode)
        for _ in range(12):
            pump(monitor, stream, np.full_like(ZERO, -.4))
        rings = (monitor.input.data, monitor.output.data)
        retained = sum(v.nbytes for v in vars(monitor.processor).values() if isinstance(v, np.ndarray))
        recover(monitor, stream)
        reference = StreamingDSP(rate, 2)
        reference.select(mode)
        expected, actual = [], []
        # Old negative history/tails must not contaminate the post-gap constant.
        for _ in range(16):
            block = np.full_like(ZERO, .5)
            expected.append(reference.process_block(block))
            actual.append(pump(monitor, stream, block))
        assert not actual[0].any()
        np.testing.assert_array_equal(np.concatenate(actual[1:]), np.concatenate(expected[:-1]))
        assert np.isfinite(actual).all() and np.max(np.abs(actual)) < 1
        assert monitor.recoveries == 1 and monitor.failed_recoveries == 0
        assert monitor.input_overflows == monitor.capture_discontinuities == 1
        assert monitor.discarded_blocks >= 1 and monitor.concealed_blocks >= 2
        assert monitor.latency_ms == pytest.approx(10 + 2048 / rate * 1000, abs=1e-5)
        assert monitor.input.data is rings[0] and monitor.output.data is rings[1]
        assert sum(v.nbytes for v in vars(monitor.processor).values() if isinstance(v, np.ndarray)) == retained
        assert "Recovered (audio lost)" in monitor.status() and "Monitor: Running" in monitor.status()


def test_input_underflow_is_also_loss_and_both_flags_count_once_per_callback():
    with session(PassThrough) as (monitor, stream):
        recover(monitor, stream, flags(input_underflow=True, input_overflow=True))
        pump(monitor, stream)
        pump(monitor, stream)
        assert monitor.input_overflows == monitor.input_underflows == 1
        assert monitor.capture_discontinuities == monitor.recoveries == 1


@pytest.mark.parametrize("persistent", [False, True])
def test_repeated_or_persistent_capture_loss_fails_closed(persistent):
    with session(PassThrough) as (monitor, stream):
        recover(monitor, stream)
        if not persistent:
            for _ in range(4):
                pump(monitor, stream)
        for _ in range(20 if persistent else 1):
            assert not stream.pump(ZERO, GAP).any()
        wait_for(lambda: not monitor.running)
        assert monitor.failed_recoveries == 1 and monitor.fatal_device_errors == 1
        assert "Repeated capture discontinuity" in monitor.error
        assert stream.closed and monitor.recovery_attempts == 1


def test_quiet_window_and_lifetime_attempt_budget_are_bounded():
    with session(PassThrough) as (monitor, stream):
        for index in range(MAX_RECOVERIES):
            if index:
                for _ in range(int(np.ceil(RECOVERY_QUIET_SECONDS * monitor.config.rate / BLOCK))):
                    pump(monitor, stream)
            recover(monitor, stream)
            pump(monitor, stream)
            pump(monitor, stream)
        assert monitor.recoveries == MAX_RECOVERIES
        for _ in range(int(np.ceil(RECOVERY_QUIET_SECONDS * monitor.config.rate / BLOCK))):
            pump(monitor, stream)
        stream.pump(ZERO, GAP)
        wait_for(lambda: not monitor.running)
        assert monitor.recovery_attempts == MAX_RECOVERIES and monitor.failed_recoveries == 1


def test_inflight_and_queued_old_audio_never_escape_after_reset():
    entered, release = threading.Event(), threading.Event()
    class Paused(PassThrough):
        def process_block(self, block):
            if block[0, 0] == -.5:
                entered.set()
                assert release.wait(2)
            return super().process_block(block)
    with session(Paused) as (monitor, stream):
        try:
            pump(monitor, stream, np.full_like(ZERO, -.25))  # queued old output
            stream.pump(np.full_like(ZERO, -.5))
            assert entered.wait(2)  # old DSP in flight
            stream.pump(np.full_like(ZERO, -.75))  # queued old input
            assert monitor.output.push(np.full_like(ZERO, -.375), stream.clock - BLOCK / stream.rate)
            assert not stream.pump(ZERO, GAP).any()
            assert not stream.pump(ZERO).any()  # callback gated while DSP in flight
            release.set()
            wait_for(lambda: monitor._recovery_ready)
            assert monitor.discarded_blocks >= 3
            assert not pump(monitor, stream, np.full_like(ZERO, .125)).any()
            np.testing.assert_array_equal(pump(monitor, stream), np.full_like(ZERO, .125))
        finally:
            release.set()


def test_recovery_deadline_does_not_wait_forever_for_worker():
    entered, release = threading.Event(), threading.Event()
    class Paused(PassThrough):
        def process_block(self, block):
            entered.set()
            assert release.wait(2)
            return super().process_block(block)
    with session(Paused) as (monitor, stream):
        try:
            stream.pump(ZERO)
            assert entered.wait(2)
            stream.pump(ZERO, GAP)
            for _ in range(RECOVERY_BLOCKS):
                assert not stream.pump(ZERO).any()
            assert monitor.halt.is_set() and monitor.failed_recoveries == 1
            assert "deadline" in monitor.error
        finally:
            release.set()
        wait_for(lambda: not monitor.running)
        assert stream.closed


@pytest.mark.parametrize("ring_name", ["input", "output"])
def test_recovery_flush_contention_stops_safely(ring_name):
    with session(PassThrough) as (monitor, stream):
        with getattr(monitor, ring_name).lock:
            stream.pump(ZERO, GAP)
            wait_for(lambda: monitor.halt.is_set())
        wait_for(lambda: not monitor.running)
        assert monitor.failed_recoveries == monitor.ring_failures == 1
        assert "Recovery buffer contention" in monitor.error


def test_device_output_flags_and_persistent_starvation_are_distinct():
    with session(PassThrough) as (monitor, stream):
        # Feed one simulated hardware callback at a time and wait for its
        # worker response. Otherwise application-ring starvation can halt the
        # session before CAPACITY driver-output flags have been delivered;
        # that is a separate failure mode tested below.
        for _ in range(CAPACITY - 1):
            pump(monitor, stream, status=flags(output_underflow=True))
        stream.pump(ZERO, flags(output_underflow=True))
        wait_for(lambda: not monitor.running)
        assert monitor.output_underflows == CAPACITY and monitor.input_underflows == 0
        assert monitor.fatal_device_errors == 1 and "device output underflow" in monitor.error
    with session(PassThrough) as (monitor, stream):
        assert not stream.pump(ZERO, flags(output_overflow=True)).any()
        wait_for(lambda: not monitor.running)
        assert monitor.output_overflows == 1 and monitor.fatal_device_errors == 1
    with session(PassThrough) as (monitor, stream):
        with monitor.output.lock:
            for _ in range(CAPACITY):
                assert not stream.pump(ZERO).any()
                # Let worker consume input, while output pushes cannot succeed.
                if monitor.halt.is_set():
                    break
        wait_for(lambda: not monitor.running)
        assert "starved" in monitor.error or "Output buffer overflow/contention" in monitor.error
        assert monitor.output_underflows == 0  # application failure, not driver


@pytest.mark.parametrize("frames", [0, 511, 1024])
def test_bad_frame_size_remains_fatal_even_during_recovery(frames):
    with session(PassThrough) as (monitor, stream):
        recover(monitor, stream)
        assert not stream.pump(ZERO, frames=frames).any()
        wait_for(lambda: not monitor.running)
        assert "callback size" in monitor.error and monitor.failed_recoveries == 1


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_samples_after_gap_are_muted_without_poisoning_state(value):
    with session() as (monitor, stream):
        recover(monitor, stream)
        for _ in range(6):
            assert not pump(monitor, stream, np.full_like(ZERO, value)).any()
        assert monitor.nonfinite == 6 and monitor.recoveries == 1


def test_nonfinite_dsp_output_still_fails_closed():
    class Invalid(PassThrough):
        def process_block(self, block):
            return np.full_like(block, np.nan)
    with session(Invalid) as (monitor, stream):
        stream.pump(ZERO)
        wait_for(lambda: not monitor.running)
        assert "invalid audio" in monitor.error


@pytest.mark.parametrize("defect", ["stale-output", "regressing", "nonfinite"])
def test_untrustworthy_timestamps_mute_and_stop(defect):
    with session(PassThrough) as (monitor, stream):
        pump(monitor, stream, np.full_like(ZERO, .25))
        if defect == "stale-output":
            stream.clock += (CAPACITY + 1) * BLOCK / stream.rate
        elif defect == "regressing":
            stream.clock -= 2 * BLOCK / stream.rate
        else:
            stream.clock = np.nan
        assert not stream.pump(ZERO).any()
        wait_for(lambda: not monitor.running)
        assert "timestamp" in monitor.error and monitor.fatal_device_errors == 1


def test_flagged_time_gap_rebases_latency_instead_of_replaying_old_queue():
    with session(PassThrough) as (monitor, stream):
        pump(monitor, stream, np.full_like(ZERO, -.5))
        stream.clock += .1
        recover(monitor, stream)
        assert not pump(monitor, stream, np.full_like(ZERO, .25)).any()
        np.testing.assert_array_equal(pump(monitor, stream), np.full_like(ZERO, .25))
        assert monitor.latency_ms == pytest.approx(10 + BLOCK / 48000 * 1000)


def test_rapid_modes_around_loss_match_new_parallel_state():
    with session() as (monitor, stream):
        for mode in MODES * 2:
            monitor.select(mode)
            pump(monitor, stream, np.full_like(ZERO, -.25))
        recover(monitor, stream)
        reference = StreamingDSP(48000, 2)
        expected, actual = [], []
        for mode in MODES * 8:
            monitor.select(mode)
            reference.select(mode)
            block = np.full_like(ZERO, .125)
            actual.append(pump(monitor, stream, block))
            expected.append(reference.process_block(block))
        np.testing.assert_array_equal(np.concatenate(actual[1:]), np.concatenate(expected[:-1]))
        assert monitor.recoveries == 1 and monitor.failed_recoveries == 0


def test_long_stable_audio_has_fixed_memory_fresh_queue_and_no_faults():
    with session() as (monitor, stream):
        arrays = (monitor.input.data, monitor.output.data, monitor.processor.history, monitor.processor.tails)
        before = sum(a.nbytes for a in arrays)
        for i in range(1000):
            monitor.select(MODES[i % 4])
            out = pump(monitor, stream, np.full_like(ZERO, .125))
            assert np.isfinite(out).all() and np.max(np.abs(out)) < 1
        assert before == sum(a.nbytes for a in arrays)
        assert monitor.input.high_water <= CAPACITY and monitor.output.high_water <= CAPACITY
        assert monitor.recovery_attempts == monitor.capture_discontinuities == monitor.device_status == 0
        assert monitor.fatal_device_errors == monitor.ring_failures == 0
        assert monitor.max_queue_age_ms <= BLOCK / 48000 * 1000 + 1e-5
        assert monitor.recovery_state == "Clean"


def test_explicit_stop_preserves_totals_new_start_resets_and_closes_sessions():
    backend = FakeBackend()
    monitor = LiveMonitor(backend, PassThrough,
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.)
    for _ in range(4):
        monitor.start("BlackHole 2ch", "Test speakers")
        assert monitor.capture_discontinuities == monitor.recovery_attempts == 0
        warmup(monitor)
        recover(monitor, monitor.stream)
        monitor.stop()
        assert monitor.capture_discontinuities == monitor.recovery_attempts == 1
        assert not monitor.running
    assert all(stream.closed for stream in backend.streams)


@pytest.mark.parametrize("defect", ["disconnect", "identity", "routing"])
def test_native_identity_and_routing_guards_still_stop_pending_recovery(defect):
    from test_live import fake_routing
    with session(PassThrough) as (monitor, stream):
        routing = fake_routing(default=11 if defect == "routing" else 10)
        expected = (99, 11) if defect == "identity" else (10, 11)
        monitor.backend.validate = lambda config: routing.validate(config.input_name, config.output_name, expected)
        # Match the fake Core Audio fixture's physical name.
        monitor.config = type(monitor.config)(0, 1, "BlackHole 2ch", "Test speakers", 48000, 2, expected)
        if defect == "disconnect":
            stream.active = False
        # No periodic-check deadline is advanced: recovery itself must validate.
        stream.pump(ZERO, GAP)
        wait_for(lambda: not monitor.running)
        assert stream.closed and monitor.fatal_device_errors == monitor.failed_recoveries == 1
        assert {"disconnect": "disconnected", "identity": "identity changed", "routing": "Single-path"}[defect] in monitor.error


def test_slow_routing_inspection_does_not_disable_recovery_deadline():
    entered, release = threading.Event(), threading.Event()
    with session(PassThrough) as (monitor, stream):
        def inspect(config):
            entered.set()
            assert release.wait(2)
        monitor.backend.validate = inspect
        try:
            stream.clock += .3
            assert entered.wait(2)
            stream.pump(ZERO, GAP)
            for _ in range(RECOVERY_BLOCKS):
                assert not stream.pump(ZERO).any()
            assert monitor.halt.is_set() and "deadline" in monitor.error
        finally:
            release.set()
        wait_for(lambda: not monitor.running)
        assert stream.closed and monitor.failed_recoveries == 1


def test_failed_dsp_reseed_stops_without_publishing_old_audio():
    constructors = []
    class CannotReseed(PassThrough):
        def __init__(self, rate, channels):
            constructors.append(threading.current_thread().name)
            if len(constructors) > 1:
                raise RuntimeError("DSP reseed failed")
            super().__init__(rate, channels)
    with session(CannotReseed) as (monitor, stream):
        pump(monitor, stream, np.full_like(ZERO, -.5))
        assert not stream.pump(ZERO, GAP).any()
        wait_for(lambda: not monitor.running)
        assert monitor.failed_recoveries == 1 and monitor.recoveries == 0
        assert monitor.output.count == 0 and stream.closed
        assert "DSP reseed failed" in monitor.error
        assert constructors[-1] == "isla-live"  # reset work never runs in callback
