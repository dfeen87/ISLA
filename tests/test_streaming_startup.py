"""LIVE startup normalization, with complete silent WOLA prehistory.

The oracle includes every emitted sample, not just delay-aligned music. It
computes frame placement and overlap sums independently of StreamingDSP state.
No audio devices are opened. Peak bounds apply only to the named control, not
arbitrary spectra: an STFT magnitude operation is not a general peak limiter.
"""
from __future__ import annotations

import numpy as np
import pytest

from isla.streaming import MODES, StreamingDSP


SIZE, HOP, DELAY = 2048, 512, 1536
STRENGTH = {"velvet": .35, "legato": .55, "melt": .75}
CONFIGURATIONS = [(44100, 1), (44100, 2), (48000, 1), (48000, 2)]


def _flush(audio):
    # Include pre-delay, the source, and the full trailing support of the last
    # nonzero analysis frame. Extra silent hops do not touch device state.
    padding = 2 * DELAY + (-len(audio)) % HOP
    return np.pad(audio, ((0, padding), (0, 0)))


def _complete_wola(audio, strength):
    """Independent full emission reference including three zero prior frames."""
    padded = _flush(audio)
    length, channels = padded.shape
    window = (.5 - .5 * np.cos(2 * np.pi * np.arange(SIZE) / SIZE))[:, None]
    numerator = np.zeros((length + DELAY + SIZE, channels))
    denominator = np.zeros((length + DELAY + SIZE, 1))
    # Negative emission starts are all-zero virtual analysis frames, but their
    # synthesis windows must still contribute normalization support at time 0.
    for emission_start in range(-DELAY, length, HOP):
        source_start = emission_start - DELAY
        frame = np.zeros((SIZE, channels))
        first, last = max(0, source_start), min(len(audio), source_start + SIZE)
        if first < last:
            frame[first - source_start:last - source_start] = audio[first:last]
        windowed = frame * window
        spectrum = np.fft.rfft(windowed, axis=0)
        magnitude = np.abs(spectrum)
        extended = np.pad(magnitude, ((1, 1), (0, 0)))
        smoothed = ((1 - strength / 2) * magnitude +
                    strength / 4 * (extended[:-2] + extended[2:]))
        # Independent oracle for the intentional LIVE-only null correction.
        # This ingress float32 representation bound is per frame/channel;
        # borrowing magnitude into an empty bin must not assign it an
        # arbitrary phase. Above the bound, the original correction applies.
        uncertainty = (np.finfo(np.float32).eps * np.sum(np.abs(windowed), axis=0, keepdims=True)
                       + (SIZE / 2) * float(np.finfo(np.float32).smallest_subnormal))
        correction_reference = spectrum / np.maximum(magnitude, uncertainty)
        reconstructed_spectrum = spectrum + (smoothed - magnitude) * correction_reference
        frame_output = np.fft.irfft(reconstructed_spectrum, n=SIZE, axis=0) * window
        first_output = emission_start + DELAY
        numerator[first_output:first_output + SIZE] += frame_output
        denominator[first_output:first_output + SIZE] += window ** 2
    numerator = numerator[DELAY:DELAY + length]
    denominator = denominator[DELAY:DELAY + length]
    # Complete 75%-overlap periodic-Hann squared support is constant 3/2.
    np.testing.assert_allclose(denominator, 1.5, atol=1e-14, rtol=0)
    return numerator / denominator


def _reference_banks(audio):
    length = len(_flush(audio))
    dry = np.zeros((length, audio.shape[1]), dtype=np.float64)
    dry[DELAY:DELAY + len(audio)] = audio
    return [dry] + [_complete_wola(audio, STRENGTH[mode]) for mode in MODES[1:]]


def _selection_reference(audio, rate, schedule):
    banks = _reference_banks(audio)
    target = np.eye(4)
    previous = target[0]
    fade = np.minimum(1., (np.arange(HOP) + 1) / round(.005 * rate))[:, None]
    result = np.empty_like(banks[0])
    for index, start in enumerate(range(0, len(result), HOP)):
        selection = target[MODES.index(schedule[index % len(schedule)])]
        mix = previous[None] + fade * (selection - previous)[None]
        result[start:start + HOP] = sum(
            bank[start:start + HOP] * mix[:, mode, None]
            for mode, bank in enumerate(banks))
        previous = selection
    return result


def _render(audio, rate, schedule):
    dsp = StreamingDSP(rate, audio.shape[1])
    initial_shapes = {key: value.shape for key, value in vars(dsp).items()
                      if isinstance(value, np.ndarray)}
    rendered = []
    for index, block in enumerate(_flush(audio).reshape(-1, HOP, audio.shape[1])):
        dsp.select(schedule[index % len(schedule)])
        rendered.append(dsp.process_block(block))
        for key, shape in initial_shapes.items():
            value = getattr(dsp, key)
            assert value.shape == shape and np.isfinite(value).all()
    return np.concatenate(rendered)


def _sources(rate, channels, family):
    count = 4096
    if family == "constant_step":
        yield np.full((count, channels), .5, np.float32)
    elif family == "20_hz_phase_grid":
        time = np.arange(count) / rate
        for phase in np.arange(4) * np.pi / 2:
            left = .5 * np.cos(2 * np.pi * 20 * time + phase)
            if channels == 1:
                yield left[:, None].astype(np.float32)
            else:
                right = .35 * np.cos(2 * np.pi * 20 * time + phase + .7)
                yield np.stack((left, right), axis=1).astype(np.float32)
    elif family == "impulse_hop_grid":
        for offset in (0, 1, 7, 219, 511, 512, 1535, 1536):
            audio = np.zeros((count, channels), np.float32)
            audio[offset] = [.5] if channels == 1 else [.5, -.35]
            yield audio
    else:
        raise AssertionError(f"Unknown test source family {family}")


@pytest.mark.parametrize("rate,channels", CONFIGURATIONS)
@pytest.mark.parametrize("mode", MODES[1:])
@pytest.mark.parametrize("family", ["constant_step", "20_hz_phase_grid", "impulse_hop_grid"])
def test_cold_wet_start_matches_complete_silent_prehistory(rate, channels, mode, family):
    for audio in _sources(rate, channels, family):
        actual = _render(audio, rate, [mode])
        reference = _selection_reference(audio, rate, [mode])
        # Includes samples 0..1535, where the former normalization failure was
        # invisible to existing tests that first removed the fixed delay.
        np.testing.assert_allclose(actual, reference, atol=1e-7, rtol=1e-6)
        residual_step = np.diff(actual.astype(np.float64) - reference, axis=0)
        np.testing.assert_allclose(residual_step, 0, atol=2e-7, rtol=0)


@pytest.mark.parametrize("rate,channels", CONFIGURATIONS)
def test_immediate_half_scale_constant_melt_has_no_startup_amplification(rate, channels):
    audio = np.full((4096, channels), .5, np.float32)
    expected = _selection_reference(audio, rate, ["melt"])
    # This named control has a bounded independently calculated response. It
    # is not a claim that modified spectra never create legitimate overshoot.
    assert np.max(np.abs(expected)) < .5
    actual = _render(audio, rate, ["melt"])
    peak = float(np.max(np.abs(actual)))
    assert peak <= .5, f"half-scale constant cold start produced peak {peak}"


@pytest.mark.parametrize("rate,channels", CONFIGURATIONS)
def test_first_and_subsequent_emissions_have_complete_squared_window_support(rate, channels):
    dsp = StreamingDSP(rate, channels)
    block = np.zeros((HOP, channels), np.float32)
    for _ in range(12):
        next_denominator = dsp.weights[:HOP] + dsp.window[:HOP] ** 2
        np.testing.assert_allclose(next_denominator, 1.5, atol=1e-14, rtol=0)
        assert not np.any(dsp.process_block(block))


@pytest.mark.parametrize("rate,channels", CONFIGURATIONS)
def test_rapid_early_mode_switches_match_complete_warm_banks(rate, channels):
    rng = np.random.default_rng(184)
    audio = rng.uniform(-.3, .3, (8192, channels)).astype(np.float32)
    schedule = ["melt", "bypass", "velvet", "legato", "melt", "bypass"]
    actual = _render(audio, rate, schedule)
    reference = _selection_reference(audio, rate, schedule)
    np.testing.assert_allclose(actual, reference, atol=1e-7, rtol=1e-6)
    edges = np.arange(HOP - 1, len(actual) - 1, HOP)
    np.testing.assert_allclose(np.diff(actual, axis=0)[edges],
                               np.diff(reference, axis=0)[edges], atol=2e-7, rtol=0)


@pytest.mark.parametrize("rate,channels", CONFIGURATIONS)
def test_default_bypass_is_exact_delayed_input_from_cold_start(rate, channels):
    audio = np.random.default_rng(185).uniform(-1.25, 1.25, (4096, channels)).astype(np.float32)
    dsp = StreamingDSP(rate, channels)
    assert dsp.mode == "bypass"
    actual = np.concatenate([dsp.process_block(block)
                             for block in _flush(audio).reshape(-1, HOP, channels)])
    reference = np.zeros_like(actual)
    reference[DELAY:DELAY + len(audio)] = audio
    np.testing.assert_array_equal(actual, reference)
