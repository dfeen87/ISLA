"""Deterministic devices are CI evidence, never native Mac listening acceptance."""
from types import SimpleNamespace
import threading
import time

import numpy as np
import pytest

from isla.coreaudio import CoreAudioRouting
from isla.live import BLOCK, CAPACITY, WARMUP_BLOCKS, BlockRing, LiveConfig, LiveMonitor, SystemCaptureBackend
from isla.monitor_gain import ListeningGainDSP, MonitorVolume
from isla.playback import AudioError, SoundDeviceBackend
from isla.streaming import MODES, StreamingDSP
from isla.terminal import TerminalController


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for audio worker")
        time.sleep(.001)


class FakeStream:
    def __init__(self, callback, rate=48000):
        self.callback = callback
        self.active = self.closed = False
        self.clock = 100.
        self.rate = rate

    def start(self):
        self.active = True

    def pump(self, data, status=None, frames=BLOCK):
        out = np.empty_like(data)
        self.callback(data, out, frames, SimpleNamespace(inputBufferAdcTime=self.clock,
                      outputBufferDacTime=self.clock + .01), status)
        self.clock += BLOCK / self.rate
        return out

    def abort(self):
        self.active = False

    def close(self):
        assert not self.closed
        self.closed = True


class FakeBackend:
    def __init__(self):
        self.streams = []
        self.failure = None
        self.route_valid = True

    def configure(self, capture, output, rate):
        if self.failure:
            raise AudioError(self.failure)
        return LiveConfig(0, 1, capture, output, rate, 2, (10, 11))

    def open(self, config, callback):
        stream = FakeStream(callback, config.rate)
        self.streams.append(stream)
        return stream

    def validate(self, config):
        if not self.route_valid:
            raise AudioError("routing changed")


class PassThrough:
    delay = 0

    def __init__(self, rate, channels):
        self.mode = "bypass"

    def select(self, mode):
        self.mode = mode

    def process_block(self, block):
        return block.copy()


def start_bypass():
    backend = FakeBackend()
    monitor = LiveMonitor(backend, processor_factory=PassThrough)
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    return monitor, backend


def warmup(monitor):
    for _ in range(WARMUP_BLOCKS):
        out = monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
        assert not out.any()


def test_pass_a_bypass_waveform_fidelity_and_responsive_lifecycle():
    backend = FakeBackend()
    # This fake is manually pumped, not a continuously firing PortAudio device.
    # Tie watchdog time to its transport frames so runner scheduling cannot
    # masquerade as missing hardware callbacks. All production monitors and
    # disconnect tests retain the real wall-clock watchdog.
    # A manually pumped fake callback is not a continuous hardware clock.
    # Hold the worker's DSP completion until the callback returns, so the
    # test exercises a deterministic one-hop pipeline rather than occasional
    # concurrent nonblocking ring push/pop contention on a busy CI runner.
    gate = threading.Event()
    gate.set()

    class ScheduledPassThrough(PassThrough):
        def process_block(self, block):
            assert gate.wait(2)
            return super().process_block(block)

    monitor = LiveMonitor(
        backend, processor_factory=ScheduledPassThrough,
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.,
    )
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    rng = np.random.default_rng(50)
    blocks = rng.uniform(-.5, .5, (12, BLOCK, 2)).astype(np.float32)
    rendered = []
    try:
        for block in blocks:
            gate.clear()
            try:
                rendered.append(monitor.stream.pump(block))
            finally:
                gate.set()
            wait_for(lambda: monitor.output.count == 1 or monitor.halt.is_set())
            assert not monitor.halt.is_set(), monitor.error
        # One transport block of delay; no smoothing, clipping or gain change.
        np.testing.assert_array_equal(np.concatenate(rendered[1:]), np.concatenate(blocks[:-1]))
        assert "Running" in monitor.status() and monitor.latency_ms > 0
        assert monitor.input.high_water <= CAPACITY and monitor.output.high_water <= CAPACITY
    finally:
        monitor.stop()
    assert backend.streams[0].closed and not monitor.running



def test_live_listening_volume_attenuates_worker_output_without_changing_bypass():
    """The real worker scales its output queue, not the original capture input."""
    backend = FakeBackend()
    volume = MonitorVolume()
    # The fake transport is pumped synchronously, unlike real PortAudio.
    # Hold the DSP worker until AFTER the callback drains the previous output
    # slot. Otherwise the synthetic worker can race ahead and collide with the
    # one-slot ring, correctly tripping the real fail-closed overflow guard.
    # This follows the established deterministic bypass transport test above.
    gate = threading.Event()
    gate.set()

    class ScheduledPassThrough(PassThrough):
        def process_block(self, block):
            assert gate.wait(2), "test DSP worker was not released after callback"
            return super().process_block(block)

    monitor = LiveMonitor(
        backend,
        processor_factory=lambda rate, channels: ListeningGainDSP(
            rate, channels, volume, delegate_factory=ScheduledPassThrough),
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.,
    )
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    signal = np.full((BLOCK, 2), .25, dtype=np.float32)

    def render_blocks(count):
        rendered = []
        for _ in range(count):
            gate.clear()
            try:
                rendered.append(monitor.stream.pump(signal))
            finally:
                gate.set()
            wait_for(lambda: monitor.output.count == 1 or monitor.halt.is_set())
            assert not monitor.halt.is_set(), monitor.error
        return rendered

    try:
        # Normal 100% output remains the exact float32 bypass waveform.
        dry = render_blocks(4)
        np.testing.assert_array_equal(dry[-1], signal)
        volume.set_percent(50)
        quiet = render_blocks(4)
        np.testing.assert_allclose(quiet[-1], signal * .5, rtol=0, atol=1e-7)
        assert np.isfinite(quiet[1]).all()
        assert (quiet[1] <= signal).all() and (quiet[1] >= signal * .5).all()
        assert monitor.mode == 'bypass' and volume.percent == 50
        volume.set_percent(0)
        muted = render_blocks(4)
        assert np.count_nonzero(muted[-1]) == 0
        volume.set_percent(100)
        restored = render_blocks(4)
        np.testing.assert_array_equal(restored[-1], signal)
        assert volume.percent == 100 and monitor.processor.mode == 'bypass'
        for invalid in (-1, 101, 50.0, True, None):
            with pytest.raises(ValueError, match="0 to 100"):
                volume.set_percent(invalid)
        assert len(backend.streams) == 1
    finally:
        monitor.stop()
    assert backend.streams[0].closed


def test_manually_pumped_transport_does_not_timeout_during_runner_pause():
    backend = FakeBackend()
    monitor = LiveMonitor(
        backend, processor_factory=PassThrough,
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.,
    )
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    try:
        # More than the real hardware heartbeat limit passes on the host.
        # The mock transport's clock has not advanced: no fake device time
        # passed, so this must not be treated as a broken physical callback.
        time.sleep(.30)
        assert monitor.running and not monitor.error
        block = np.ones((BLOCK, 2), np.float32) * .25
        monitor.stream.pump(block)
        wait_for(lambda: monitor.output.count == 1)
        output = monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
        np.testing.assert_array_equal(output, block)
    finally:
        monitor.stop()


def test_real_watchdog_still_detects_missing_callbacks():
    monitor, backend = start_bypass()
    try:
        # A real clock is the default; absence of further callbacks must
        # still halt the session, even while a mock stream reports active.
        wait_for(lambda: not monitor.running)
        assert "callbacks stopped" in monitor.error
        assert backend.streams[0].closed
    finally:
        monitor.stop()


def fake_routing(default=10, transport="bltn"):
    routing = CoreAudioRouting.__new__(CoreAudioRouting)
    routing.snapshot = lambda: ([
        dict(id=10, name="BlackHole 2ch", transport="virt", alive=True, input=True, output=True),
        dict(id=11, name="Test speakers", transport=transport, alive=True, input=False, output=True),
    ], default)
    routing.validate_stream = lambda sd, stream, expected: None
    return routing


@pytest.mark.parametrize("transport", ["virt", "grup", "????"])
def test_pass_a_reject_virtual_aggregate_and_unknown_outputs(transport):
    with pytest.raises(AudioError, match="physical"):
        fake_routing(transport=transport).validate("BlackHole 2ch", "Test speakers")


def test_pass_a_single_path_and_feedback_guards():
    assert fake_routing().validate("BlackHole 2ch", "Test speakers") == (10, 11)
    with pytest.raises(AudioError, match="Single-path") as exc:
        fake_routing(default=11).validate("BlackHole 2ch", "Test speakers")
    assert "currently 'Test speakers'" in str(exc.value)
    assert "Keep 'Test speakers' as the physical output selected inside ISLA" in str(exc.value)
    assert "System Settings > Sound > Output to BlackHole 2ch" in str(exc.value)
    # An unidentified or unplugged macOS default must fail closed with usable guidance.
    with pytest.raises(AudioError, match="currently 'Unknown device'"):
        fake_routing(default=99).validate("BlackHole 2ch", "Test speakers")
    with pytest.raises(AudioError, match="physical"):
        fake_routing().validate("BlackHole 2ch", "BlackHole 2ch")
    with pytest.raises(AudioError, match="missing"):
        fake_routing().validate("Microphone", "Test speakers")
    with pytest.raises(AudioError, match="identity changed"):
        fake_routing().validate("BlackHole 2ch", "Test speakers", (99, 11))


def mock_playback():
    backend = SoundDeviceBackend.__new__(SoundDeviceBackend)
    backend.output_device = None
    devices = [dict(name="BlackHole 2ch", max_input_channels=2, max_output_channels=2),
               dict(name="Test speakers", max_input_channels=0, max_output_channels=2),
               dict(name="Microphone", max_input_channels=1, max_output_channels=0)]
    backend.sd = SimpleNamespace(query_devices=lambda: devices,
        check_input_settings=lambda **kw: None, check_output_settings=lambda **kw: None)
    return backend, devices


def test_pass_a_discovery_explicit_devices_and_sample_rate_validation():
    playback, devices = mock_playback()
    assert playback.devices()[0]["index"] == 0
    assert playback.select_output("1") == "Test speakers"
    backend = SystemCaptureBackend(playback, fake_routing())
    for rate in (44100, 48000):
        config = backend.configure("0", playback.output_device, rate)
        assert config.input_id == 0 and config.output_id == 1 and config.rate == rate
        backend.validate(config)
    with pytest.raises(AudioError, match="missing"):
        backend.configure("absent", "Test speakers", 48000)
    with pytest.raises(AudioError, match="standalone"):
        backend.configure("Microphone", "Test speakers", 48000)
    with pytest.raises(AudioError, match="rate"):
        backend.configure("0", "1", 96000)
    with pytest.raises(AudioError, match="Choose a physical"):
        backend.configure("0", None, 48000)
    devices[1]["max_output_channels"] = 1
    with pytest.raises(AudioError, match="stereo"):
        backend.configure("0", "1", 48000)


def test_pass_a_clean_repeated_starts_stops_and_failed_initialization():
    monitor, backend = start_bypass()
    monitor.stop()
    for _ in range(10):
        monitor.start("BlackHole 2ch", "Test speakers")
        assert "already" in monitor.start("BlackHole 2ch", "Test speakers")
        monitor.stop()
        monitor.stop()
    backend.failure = "missing device"
    with pytest.raises(AudioError, match="missing device"):
        monitor.start("BlackHole 2ch", "Test speakers")
    assert monitor.stream is None and not monitor.running
    backend.failure = None
    monitor.start("BlackHole 2ch", "Test speakers")
    monitor.stop()
    assert all(stream.closed for stream in backend.streams)


@pytest.mark.parametrize("route_change", [False, True])
def test_pass_a_disconnection_or_routing_change_closes_without_terminal_poll(route_change):
    monitor, backend = start_bypass()
    if route_change:
        backend.route_valid = False
        # Keep callbacks alive until the periodic routing check.
        deadline = time.monotonic() + .5
        while monitor.running and time.monotonic() < deadline:
            monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
            time.sleep(.01)
    else:
        monitor.stream.active = False
    wait_for(lambda: not monitor.running)
    assert monitor.state == "Failed" and backend.streams[0].closed
    monitor.stop()


def test_pass_a_bounded_ring_and_nonblocking_contention():
    ring = BlockRing(2)
    data = np.ones((BLOCK, 2), np.float32)
    for i in range(CAPACITY):
        assert ring.push(data * i, i)
    assert not ring.push(data, 9) and ring.count == CAPACITY
    target = np.empty_like(data)
    for i in range(CAPACITY):
        assert ring.pop_into(target) == i
        np.testing.assert_array_equal(target, data * i)
    assert ring.pop_into(target) is None
    with ring.lock:
        assert not ring.push(data, 0) and ring.pop_into(target) is None
    assert ring.data.nbytes == CAPACITY * BLOCK * 2 * 4


def test_pass_a_partial_start_failure_releases_stream():
    monitor = LiveMonitor(FakeBackend(), PassThrough)
    backend = monitor.backend
    original = backend.open
    def fail(config, callback):
        stream = original(config, callback)
        def start():
            raise AudioError("start failed")
        stream.start = start
        return stream
    backend.open = fail
    with pytest.raises(AudioError, match="start failed"):
        monitor.start("BlackHole 2ch", "Test speakers")
    assert backend.streams[0].closed and monitor.stream is None


def batch_reference(audio, strength):
    """Independent whole-signal WOLA reference with no transport chunk edges."""
    size, hop = 2048, 512
    window = .5 - .5 * np.cos(2 * np.pi * np.arange(size) / size)
    padded = np.pad(audio, ((size - hop, size), (0, 0)))
    frames = np.stack([padded[i:i + size] for i in range(0, len(padded) - size + 1, hop)])
    windowed = frames * window[None, :, None]
    spectrum = np.fft.rfft(windowed, axis=1)
    mag = np.abs(spectrum)
    extended = np.pad(mag, ((0, 0), (1, 1), (0, 0)))
    smooth = .25 * extended[:, :-2] + .5 * extended[:, 1:-1] + .25 * extended[:, 2:]
    # Independent expression of the intentional LIVE null-phase correction.
    # The archived study/frozen baseline retains the previous phase formula.
    # Numerical comparison tolerances below remain unchanged.
    uncertainty = np.finfo(np.float32).eps * np.sum(np.abs(windowed), axis=1, keepdims=True)
    uncertainty += .5 * float(np.finfo(np.float32).smallest_subnormal) * size
    unit = spectrum / np.maximum(mag, uncertainty)
    modified = spectrum + (((1 - strength) * mag + strength * smooth) - mag) * unit
    result = np.fft.irfft(modified, n=size, axis=1) * window[None, :, None]
    total = np.zeros_like(padded, dtype=np.float64)
    weights = np.zeros(len(padded))
    for index, frame in enumerate(result):
        start = index * hop
        total[start:start + size] += frame
        weights[start:start + size] += window ** 2
    total /= np.maximum(weights[:, None], 1e-8)
    return total[size - hop:size - hop + len(audio)]


def signal(channels, count=BLOCK * 24, sr=48000):
    t = np.arange(count) / sr
    # Partial-rich changing piano-like attacks, with distinct stereo content.
    envelope = np.exp(-12 * np.remainder(t, .07))
    mono = envelope * sum(.18 / k * np.sin(2 * np.pi * 261.63 * k * t + .12 * k)
                          for k in range(1, 8))
    return np.stack([mono if c == 0 else .6 * np.roll(mono, 53) for c in range(channels)], axis=1).astype(np.float32)


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("mode,strength", [("velvet", .35), ("legato", .55), ("melt", .75)])
def test_pass_b_continuity_matches_whole_signal_nonzero_reference(rate, channels, mode, strength):
    audio = signal(channels, sr=rate)
    dsp = StreamingDSP(rate, channels)
    dsp.select(mode)
    padded = np.pad(audio, ((0, dsp.delay), (0, 0)))
    rendered = np.concatenate([dsp.process_block(padded[i:i + BLOCK]) for i in range(0, len(padded), BLOCK)])
    rendered = rendered[dsp.delay:]
    reference = batch_reference(audio, strength)
    np.testing.assert_allclose(rendered, reference, atol=1e-7, rtol=1e-6)
    edges = np.arange(BLOCK, len(audio), BLOCK)
    np.testing.assert_allclose(rendered[edges - 1], reference[edges - 1], atol=1e-7)
    np.testing.assert_allclose(rendered[edges], reference[edges], atol=1e-7)
    # Real DSP: at least 1% RMS difference, relative to the original waveform.
    assert np.sqrt(np.mean((rendered - audio) ** 2)) / np.sqrt(np.mean(audio ** 2)) > .01
    if channels == 2:
        assert not np.array_equal(rendered[:, 0], rendered[:, 1])


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
def test_pass_b_exact_delayed_bypass_and_silence_nonfinite(rate, channels):
    audio = signal(channels, sr=rate)
    dsp = StreamingDSP(rate, channels)
    padded = np.pad(audio, ((0, dsp.delay), (0, 0)))
    rendered = np.concatenate([dsp.process_block(padded[i:i + BLOCK]) for i in range(0, len(padded), BLOCK)])
    assert not np.any(rendered[:dsp.delay])
    np.testing.assert_array_equal(rendered[dsp.delay:], audio)
    dsp = StreamingDSP(rate, channels)
    for mode in MODES:
        dsp.select(mode)
        for value in (0., np.nan, np.inf, -np.inf):
            assert not np.any(dsp.process_block(np.full((BLOCK, channels), value, np.float32)))


def test_pass_b_switch_crossfade_matches_warm_parallel_states():
    audio = signal(2)
    dsp = StreamingDSP(48000, 2)
    references = [StreamingDSP(48000, 2) for _ in MODES]
    for ref, mode in zip(references, MODES):
        ref.select(mode)
    old = "bypass"
    modes = ["bypass"] * 4 + ["velvet", "legato", "melt", "bypass"] * 5
    for i, mode in enumerate(modes):
        block = audio[i * BLOCK:(i + 1) * BLOCK]
        banks = [ref.process_block(block) for ref in references]
        dsp.select(mode)
        actual = dsp.process_block(block)
        if i < 4:
            expected = banks[0]
        else:
            expected = (banks[MODES.index(old)] * (1 - dsp.fade) + banks[MODES.index(mode)] * dsp.fade)
        np.testing.assert_allclose(actual, expected, atol=1e-7)
        old = mode


@pytest.mark.parametrize("rate", [44100, 48000])
def test_pass_b_live_worker_actual_modes_and_timing(rate):
    monitor = LiveMonitor(FakeBackend())
    monitor.start("BlackHole 2ch", "Test speakers", rate)
    warmup(monitor)
    audio = signal(2, count=BLOCK * 48, sr=rate)
    captured = []
    try:
        for index in range(48):
            mode = MODES[index // 12]
            monitor.select(mode)
            stream = monitor.stream
            captured.append(stream.pump(audio[index * BLOCK:(index + 1) * BLOCK]))
            wait_for(lambda: monitor.output.count == 1)
        actual = np.concatenate(captured)
        np.testing.assert_array_equal(actual[BLOCK * 4:BLOCK * 12], audio[:BLOCK * 8])
        for i in range(1, 4):
            begin, end = (i * 12 + 6) * BLOCK, (i + 1) * 12 * BLOCK
            dry = audio[begin - 2048:end - 2048]
            assert np.sqrt(np.mean((actual[begin:end] - dry) ** 2)) > .001
        assert monitor.latency_ms == pytest.approx(10 + 2048 / rate * 1000, abs=1e-5)
        assert monitor.underflows == 1 and monitor.overflows == 0
    finally:
        monitor.stop()
    assert not monitor.running


def test_pass_b_underflow_zero_fill_overflow_shutdown_and_memory_bound():
    monitor, backend = start_bypass()
    # Prevent worker consumption while filling rings through the callback.
    with monitor.input.lock:
        out = monitor.stream.pump(np.ones((BLOCK, 2), np.float32))
    assert not out.any() and monitor.overflows == 1
    wait_for(lambda: not monitor.running)
    assert backend.streams[0].closed and "overflow" in monitor.error
    monitor.stop()
    # Underflows are silence, and repeated starvation shuts down automatically.
    monitor, backend = start_bypass()
    with monitor.output.lock:
        for _ in range(CAPACITY):
            out = monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
            assert not out.any()
    wait_for(lambda: not monitor.running)
    assert monitor.underflows == CAPACITY and "starved" in monitor.error
    assert monitor.input.count <= CAPACITY and monitor.output.count <= CAPACITY
    monitor.stop()


def test_pass_b_bad_input_device_status_and_processor_failure_are_safe():
    # This test manually pumps a fake stream. Wall-clock watchdog time can
    # advance on a busy hosted Mac runner while no fake callback is scheduled,
    # causing an unrelated disconnect before the intended recovery assertions.
    # Production monitoring and separate watchdog tests still use real time.
    backend = FakeBackend()
    monitor = LiveMonitor(
        backend, processor_factory=PassThrough,
        monotonic_clock=lambda: backend.streams[-1].clock if backend.streams else 100.,
    )
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    try:
        monitor.stream.pump(np.full((BLOCK, 2), np.nan, np.float32))
        wait_for(lambda: monitor.output.count == 1)
        out = monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
        assert not out.any() and monitor.nonfinite == 1
        monitor.stream.pump(np.zeros((BLOCK, 2), np.float32),
                            SimpleNamespace(input_overflow=True, input_underflow=False))
        assert monitor.recovery_attempts == 1 and not monitor.halt.is_set()
        monitor.stream.pump(np.zeros((BLOCK, 2), np.float32),
                            SimpleNamespace(input_overflow=True, input_underflow=False))
        wait_for(lambda: not monitor.running)
        assert monitor.device_status == 2 and "discontinuity" in monitor.error
        assert monitor.failed_recoveries == 1
    finally:
        monitor.stop()
    class Broken(PassThrough):
        def process_block(self, block):
            raise RuntimeError("DSP failed")
    monitor = LiveMonitor(backend, Broken)
    monitor.start("BlackHole 2ch", "Test speakers")
    warmup(monitor)
    monitor.stream.pump(np.zeros((BLOCK, 2), np.float32))
    wait_for(lambda: not monitor.running)
    assert "DSP failed" in monitor.error and backend.streams[-1].closed
    monitor.stop()


def test_native_startup_status_is_discarded_before_any_processing():
    monitor = LiveMonitor(FakeBackend(), PassThrough)
    monitor.start("BlackHole 2ch", "Test speakers")
    try:
        for _ in range(WARMUP_BLOCKS):
            out = monitor.stream.pump(np.ones((BLOCK, 2), np.float32),
                SimpleNamespace(input_overflow=True, input_underflow=False))
            assert not out.any()
        assert monitor.running and monitor.input.count == 0 and monitor.output.count == 0
        monitor.stream.pump(np.zeros((BLOCK, 2), np.float32),
            SimpleNamespace(input_overflow=True, input_underflow=False))
        wait_for(lambda: not monitor.running)
        assert "Repeated capture discontinuity" in monitor.error
        assert monitor.input_overflows == WARMUP_BLOCKS + 1
        assert monitor.recovery_attempts == 0
    finally:
        monitor.stop()


def test_pass_b_state_memory_stays_fixed_for_long_stream():
    dsp = StreamingDSP(48000, 2)
    block = signal(2, BLOCK)
    size = sum(v.nbytes for v in vars(dsp).values() if isinstance(v, np.ndarray))
    for i in range(1000):
        dsp.select(MODES[i % 4])
        result = dsp.process_block(block)
        assert result.shape == block.shape and np.isfinite(result).all()
    assert sum(v.nbytes for v in vars(dsp).values() if isinstance(v, np.ndarray)) == size
    assert size < 200_000


def test_pass_b_invalid_shapes_rates_and_modes():
    for rate, channels in [(8000, 2), (48000, 3)]:
        with pytest.raises(ValueError):
            StreamingDSP(rate, channels)
    dsp = StreamingDSP(48000, 2)
    with pytest.raises(ValueError):
        dsp.process_block(np.zeros((511, 2)))
    with pytest.raises(ValueError):
        dsp.select("unknown")


def test_terminal_live_commands_preserve_file_buffers_and_exit_closes_audio():
    playback, devices = mock_playback()
    devices[0]["default_samplerate"] = devices[1]["default_samplerate"] = devices[2]["default_samplerate"] = 48000
    backend = FakeBackend()
    terminal = TerminalController(playback, live_backend=backend)
    original = np.zeros((2048, 2), np.float32)
    terminal.player.install({"original": original}, 48000)
    assert "BlackHole" in terminal.execute("DEVICES")
    assert "System audio" in terminal.execute("SOURCE SYSTEM")
    assert "BlackHole" in terminal.execute('INPUT "BlackHole 2ch"')
    assert "Test speakers" in terminal.execute('OUTPUT "Test speakers"')
    assert "active" in terminal.execute("MONITOR START 44100")
    for mode in ("velvet", "legato", "melt"):
        assert mode.upper() in terminal.execute(f"mode {mode}")
        assert terminal.live.mode == mode
    assert "Original system" in terminal.execute("bypass")
    status = terminal.execute("status")
    assert all(value in status for value in ("System Audio", "Bypass", "Running", "44100", "BlackHole", "Test speakers"))
    assert "already running" in terminal.execute("play")
    assert len(backend.streams) == 1
    for command in ('output "Test speakers"', 'input "BlackHole 2ch"', "pause", "load example.wav"):
        with pytest.raises(ValueError):
            terminal.execute(command)
    assert "stopped" in terminal.execute("MONITOR STOP")
    assert "File source" in terminal.execute("source file")
    assert terminal.player.buffers["original"] is original
    terminal.execute("source system")
    terminal.execute("monitor start")
    assert "Resources released" in terminal.execute("exit")
    assert terminal.closed and not terminal.live.running
    assert all(stream.closed for stream in backend.streams)


@pytest.mark.parametrize("command", ["source", "source mic", "monitor", "monitor start 8000", "monitor dance"])
def test_terminal_invalid_live_commands(command):
    playback, _ = mock_playback()
    terminal = TerminalController(playback, live_backend=FakeBackend())
    terminal.execute("source system")
    try:
        with pytest.raises(ValueError):
            terminal.execute(command)
    finally:
        terminal.close()


def test_backend_rejects_unsupported_settings_and_opens_explicit_duplex():
    playback, _ = mock_playback()
    backend = SystemCaptureBackend(playback, fake_routing())
    config = backend.configure("0", "1", 48000)
    opened = []
    playback.sd.Stream = lambda **kw: opened.append(kw)
    backend.open(config, "callback")
    assert opened == [dict(device=(0, 1), samplerate=48000, channels=(2, 2),
                           dtype="float32", blocksize=BLOCK, latency="low", callback="callback")]
    def fail(**kw):
        raise RuntimeError("unsupported rate")
    playback.sd.check_input_settings = fail
    with pytest.raises(AudioError, match="unsupported rate"):
        backend.configure("0", "1", 44100)


def test_coreaudio_direction_disambiguates_split_bluetooth_devices():
    routing = fake_routing()
    entries, default = routing.snapshot()
    entries.append(dict(id=12, name="Test speakers", alive=True, transport="blue", input=True, output=False))
    routing.snapshot = lambda: (entries, default)
    assert routing.validate("BlackHole 2ch", "Test speakers") == (10, 11)
    entries.append(dict(id=13, name="Test speakers", alive=True, transport="usb ", input=False, output=True))
    with pytest.raises(AudioError, match="ambiguous"):
        routing.validate("BlackHole 2ch", "Test speakers")


def test_file_preparation_error_cannot_block_live_stop():
    playback, _ = mock_playback()
    terminal = TerminalController(playback, live_backend=FakeBackend())
    terminal.execute("source system")
    terminal.execute('output "Test speakers"')
    terminal.execute("monitor start")
    def failed_poll():
        raise RuntimeError("old file preparation failed")
    terminal.job = SimpleNamespace(done=False, poll=failed_poll, close=lambda: None)
    assert "stopped" in terminal.execute("monitor stop")
    assert not terminal.live.running
    terminal.close()


def test_fft_executes_on_worker_never_callback(monkeypatch):
    original = np.fft.rfft
    threads = []
    def checked(*args, **kwargs):
        name = threading.current_thread().name
        assert name == "isla-live"
        threads.append(name)
        return original(*args, **kwargs)
    monkeypatch.setattr(np.fft, "rfft", checked)
    monitor = LiveMonitor(FakeBackend())
    try:
        monitor.start("BlackHole 2ch", "Test speakers")
        warmup(monitor)
        monitor.stream.pump(signal(2, BLOCK))
        wait_for(lambda: monitor.output.count == 1)
        assert threads == ["isla-live"]
    finally:
        monitor.stop()


def test_opened_native_stream_identity_guard_fails_closed():
    routing = CoreAudioRouting.__new__(CoreAudioRouting)
    routing._stream_identity = lambda sd, stream: (10, 11)
    routing.validate_stream(None, None, (10, 11))
    with pytest.raises(AudioError, match="identity differs"):
        routing.validate_stream(None, None, (10, 10))
    def unavailable(sd, stream):
        raise AttributeError("missing PortAudio extension")
    routing._stream_identity = unavailable
    with pytest.raises(AudioError, match="Cannot verify"):
        routing.validate_stream(None, None, (10, 11))


def test_failed_native_identity_check_closes_inactive_stream():
    playback, _ = mock_playback()
    routing = fake_routing()
    backend = SystemCaptureBackend(playback, routing)
    config = backend.configure("0", "1", 48000)
    stream = FakeStream(None)
    playback.sd.Stream = lambda **kw: stream
    def stale(sd, stream, expected):
        raise AudioError("stale native IDs")
    routing.validate_stream = stale
    with pytest.raises(AudioError, match="stale native IDs"):
        backend.open(config, None)
    assert stream.closed and not stream.active


def test_guided_audio_setup_lists_verified_devices_and_configures_without_starting():
    """A numeric wizard selection must not select an input-only/virtual output."""
    from isla.terminal import run_terminal

    playback, devices = mock_playback()
    devices.append(dict(name="Microsoft Teams Audio", max_input_channels=1, max_output_channels=2))
    devices.append(dict(name="Mono speaker", max_input_channels=0, max_output_channels=1))
    routing = fake_routing()
    backend = FakeBackend()
    controller = TerminalController(playback, live_backend=backend, routing=routing)
    try:
        options = controller.execute("setup audio")
        assert "Available capture inputs:" in options and "[0] BlackHole 2ch" in options
        assert "BlackHole 2ch" in controller.execute("0")
        assert controller.setup_prompt.startswith("Select output")
        prompt = controller._audio_setup_menu("Outputs:", controller._setup_outputs)
        assert "[1] Test speakers" in prompt
        assert "BlackHole" not in prompt
        assert "Microsoft Teams" not in prompt
        assert "Mono speaker" not in prompt
        assert "Microphone" not in prompt
        assert "Not an eligible physical stereo output" in controller.execute("2")
        assert "Not an eligible physical stereo output" in controller.execute("0")
        assert controller.source == "file" and controller.output is None
        result = controller.execute("1")
        assert "ISLA devices selected: capture from BlackHole 2ch -> playback to Test speakers." in result
        assert "NOT changed or verified" in result
        assert "System Settings > Sound > Output" in result
        assert "(NOT Test speakers)" in result
        assert "monitor start" in result
        assert controller.source == "system"
        assert controller.capture == "BlackHole 2ch"
        assert controller.output == "Test speakers"
        assert not controller.live.running and not backend.streams
        assert controller.setup_prompt == "isla> "
        assert "Selected output: Test speakers" in controller.execute("status")
        # Backward-compatible manual device commands remain supported.
        assert "Test speakers" in controller.execute("output 1")
    finally:
        controller.close()


def test_guided_audio_setup_cancel_and_invalid_choices_preserve_state():
    playback, _ = mock_playback()
    controller = TerminalController(playback, live_backend=FakeBackend(), routing=fake_routing())
    try:
        controller.execute("setup audio")
        assert "Not an eligible input" in controller.execute("2")
        assert controller._setup_stage == "input"
        assert "canceled" in controller.execute("cancel")
        assert controller.source == "file" and controller.output is None
        controller.execute("setup audio")
        controller.execute('"BlackHole 2ch"')
        assert "Not an eligible physical stereo output" in controller.execute("1:")
        assert "Test speakers" in controller.execute('"Test speakers"')
        assert controller.source == "system"
    finally:
        controller.close()


def test_guided_audio_setup_fails_closed_on_unknown_routing_and_hotplug():
    playback, devices = mock_playback()
    def unavailable():
        raise AudioError("Core Audio inspection failed")
    controller = TerminalController(playback, live_backend=FakeBackend(),
                                    routing=SimpleNamespace(snapshot=unavailable))
    try:
        with pytest.raises(AudioError, match="inspection failed"):
            controller.execute("setup audio")
        assert controller.setup_prompt == "isla> "
        assert controller.source == "file" and controller.output is None
    finally:
        controller.close()

    controller = TerminalController(playback, live_backend=FakeBackend(), routing=fake_routing())
    try:
        controller.execute("setup audio")
        controller.execute("0")
        devices[1]["name"] = "Renamed headphones"  # Stale PortAudio mapping: fail, never silently reroute.
        with pytest.raises(AudioError):
            controller.execute("1")
        assert controller.source == "file" and controller.output is None
        assert controller.setup_prompt == "isla> "
    finally:
        controller.close()


def test_guided_audio_setup_interactive_prompt_and_ctrl_c_cancel():
    from isla.terminal import run_terminal

    playback, _ = mock_playback()
    prompts = []
    answers = iter(["setup audio", "0", "1", "status", "exit"])
    def prompt_input(prompt):
        prompts.append(prompt)
        return next(answers)
    output = []
    assert run_terminal(prompt_input, output.append, playback, routing=fake_routing()) == 0
    assert prompts[:4] == ["isla> ", "Select input (number/name or cancel): ",
                           "Select output (number/name or cancel): ", "isla> "]
    assert any("ISLA devices selected:" in message for message in output)
    assert any("macOS system audio routing is NOT changed or verified" in message for message in output)
    assert any("Selected output: Test speakers" in message for message in output)
    assert any("Goodbye from ISLA" in message for message in output)

    playback, _ = mock_playback()
    prompts, output = [], []
    answers = iter(["setup audio", KeyboardInterrupt(), "help", "exit"])
    def cancel_input(prompt):
        prompts.append(prompt)
        answer = next(answers)
        if isinstance(answer, KeyboardInterrupt):
            raise answer
        return answer
    assert run_terminal(cancel_input, output.append, playback, routing=fake_routing()) == 0
    assert prompts == ["isla> ", "Select input (number/name or cancel): ", "isla> ", "isla> "]
    assert any("setup canceled" in message for message in output)
    assert any("setup audio" in message for message in output)


def test_guided_audio_setup_rejects_started_audio():
    playback, _ = mock_playback()
    controller = TerminalController(playback, live_backend=FakeBackend(), routing=fake_routing())
    # Simulate a currently owned file-playback stream without opening physical hardware.
    controller.player.stream = object()
    try:
        with pytest.raises(ValueError, match="Stop LIVE monitoring"):
            controller.execute("setup audio")
        assert controller.setup_prompt == "isla> "
    finally:
        controller.player.stream = None
        controller.close()
