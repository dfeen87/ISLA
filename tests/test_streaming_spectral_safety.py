"""LIVE reconstruction robustness; no audio devices or musical-quality claims.

The perturbation regression was added and executed against the unchanged
legacy reconstruction before any spectral correction. The input change is
below one float32 epsilon in relative RMS; percent-scale output changes are
an unstable phase assignment, not intentional musical processing.
"""
import numpy as np
import pytest

from isla.streaming import StreamingDSP
from isla.spectral import phase_reference, reconstruct_spectrum


def _render(audio, rate, mode):
    dsp = StreamingDSP(rate, audio.shape[1])
    dsp.select(mode)
    padded = np.pad(audio, ((0, dsp.delay), (0, 0)))
    rendered = np.concatenate([dsp.process_block(padded[i:i + dsp.hop])
                               for i in range(0, len(padded), dsp.hop)])
    return rendered[dsp.delay:dsp.delay + len(audio)]


def _relative(actual, reference):
    a = actual.astype(np.float64)
    b = reference.astype(np.float64)
    return np.linalg.norm(a - b) / np.linalg.norm(b)


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("bin_index", [20, 40])
@pytest.mark.parametrize("mode", ["velvet", "legato", "melt"])
def test_near_null_quantization_scale_perturbation_has_no_percent_scale_output_change(
    rate, channels, bin_index, mode
):
    count = 65536
    time = np.arange(count) / rate
    mono = (.5 * np.sin(2 * np.pi * bin_index * rate / 2048 * time)).astype(np.float32)
    audio = mono[:, None] if channels == 1 else np.stack((mono, np.float32(.6) * mono), axis=1)
    noise = np.random.default_rng(72).normal(size=audio.shape) * 1e-8
    changed = (audio.astype(np.float64) + noise).astype(np.float32)
    # Exclude startup and end flush: this probes persistent spectral-null
    # sensitivity independently of incomplete startup WOLA normalization.
    region = slice(4096, -4096)
    assert _relative(changed[region], audio[region]) < np.finfo(np.float32).eps
    reference = _render(audio, rate, mode)[region]
    perturbed = _render(changed, rate, mode)[region]
    # New representation-stability requirement, not a relaxed legacy WOLA
    # reference tolerance and not an audibility/quality threshold.
    assert _relative(perturbed, reference) < .01


@pytest.mark.parametrize("kind", ["negative_dc", "negative_nyquist", "random"])
def test_real_rfft_endpoints_discard_angle_roundoff_without_audio_change(kind):
    if kind == "negative_dc":
        audio = np.full((2048, 2), -.5)
    elif kind == "negative_nyquist":
        audio = np.repeat((-.5 * (-1.) ** np.arange(2048))[:, None], 2, axis=1)
    else:
        audio = np.random.default_rng(196).normal(size=(2048, 2))
    spectrum = np.fft.rfft(audio, axis=0)
    magnitude = np.abs(spectrum)
    extended = np.pad(magnitude, ((1, 1), (0, 0)))
    smoothed = .625 * magnitude + .1875 * (extended[:-2] + extended[2:])
    legacy = smoothed * np.exp(1j * np.angle(spectrum))
    real_endpoints = legacy.copy()
    real_endpoints[[0, -1]] = real_endpoints[[0, -1]].real
    # np.exp(1j*pi) has a tiny imaginary residue; irfft ignores imaginary
    # DC/Nyquist values. No endpoint-only audible defect is asserted.
    np.testing.assert_array_equal(np.fft.irfft(legacy, n=2048, axis=0),
                                  np.fft.irfft(real_endpoints, n=2048, axis=0))


def test_above_uncertainty_reconstruction_matches_legacy_and_real_endpoints():
    # Every original bin has a substantial magnitude, including negative
    # real endpoints. This should retain the original musical operation.
    spectrum = np.array([[-3., -2.], [1.+2j, -2.+1j], [2.-1j, -1.-2j],
                         [2.+3j, -3.+2j], [-1., -4.]], dtype=np.complex128)
    windowed = np.fft.irfft(spectrum, n=8, axis=0)
    magnitude = np.abs(spectrum)
    padded = np.pad(magnitude, ((1, 1), (0, 0)))
    smoothed = .625 * magnitude + .1875 * (padded[:-2] + padded[2:])
    reference = phase_reference(spectrum, magnitude, windowed)
    output = reconstruct_spectrum(spectrum, magnitude, smoothed, reference)
    np.testing.assert_allclose(output, smoothed * np.exp(1j * np.angle(spectrum)),
                               atol=2e-15, rtol=2e-15)
    np.testing.assert_array_equal(output[[0, -1]].imag, 0.)


def test_correction_vanishes_continuously_at_an_exact_null():
    spectra = []
    for phase in (0., np.pi / 2, np.pi, -np.pi / 2):
        output_magnitudes = []
        for amplitude in (0., 1e-12, 1e-14, 1e-16):
            spectrum = np.array([[0.], [1.], [amplitude * np.exp(1j * phase)],
                                 [1.], [0.]], dtype=np.complex128)
            magnitude = np.abs(spectrum)
            windowed = np.fft.irfft(spectrum, n=8, axis=0)
            padded = np.pad(magnitude, ((1, 1), (0, 0)))
            smoothed = .625 * magnitude + .1875 * (padded[:-2] + padded[2:])
            assert smoothed[2, 0] > .3  # The legacy null would receive finite energy.
            output = reconstruct_spectrum(
                spectrum, magnitude, smoothed, phase_reference(spectrum, magnitude, windowed)
            )
            output_magnitudes.append(abs(output[2, 0]))
        assert output_magnitudes[0] == 0.
        # A 100-fold smaller coefficient produces a 100-fold smaller result,
        # independently of the approach angle. No phase is invented at zero.
        np.testing.assert_allclose(np.array(output_magnitudes[2:]) /
                                   np.array(output_magnitudes[1:-1]), .01,
                                   rtol=1e-8, atol=0.)
        spectra.append(output_magnitudes)
    np.testing.assert_allclose(spectra, np.broadcast_to(spectra[0], (4, 4)),
                               rtol=1e-8, atol=0.)


@pytest.mark.parametrize("subnormal", [False, True])
def test_zero_strength_and_silence_or_subnormal_input_remain_finite(subnormal):
    window = (.5 - .5 * np.cos(2 * np.pi * np.arange(2048) / 2048))[:, None]
    if subnormal:
        smallest = float(np.finfo(np.float32).smallest_subnormal)
        audio = np.full((2048, 2), smallest)
        audio[::2, 1] *= -1
    else:
        audio = np.zeros((2048, 2))
    windowed = audio * window
    spectrum = np.fft.rfft(windowed, axis=0)
    magnitude = np.abs(spectrum)
    reference = phase_reference(spectrum, magnitude, windowed)
    assert np.isfinite(reference).all()
    zero_strength = reconstruct_spectrum(spectrum, magnitude, magnitude, reference)
    np.testing.assert_array_equal(zero_strength, spectrum)
    if not subnormal:
        np.testing.assert_array_equal(reference, 0.)
        np.testing.assert_array_equal(zero_strength, 0.)
