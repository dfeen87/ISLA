import numpy as np
import pytest
from phased_music_notes.harmonics import HarmonicBlender

def generate_harmonic_signal(sr=44100):
    t = np.linspace(0, 1.0, sr, endpoint=False)

    # Fundamental + several harmonics
    freqs = [440, 880, 1320, 1760, 2200, 4400, 8800]
    amps = [1.0, 0.5, 0.3, 0.2, 0.1, 0.05, 0.02]

    signal = np.zeros(sr)
    for f, a in zip(freqs, amps):
        signal += a * np.sin(2 * np.pi * f * t)

    # Normalize
    signal /= np.max(np.abs(signal))

    return signal

def test_harmonic_blender_mono():
    sr = 44100
    signal = generate_harmonic_signal(sr)

    blender = HarmonicBlender(strength=1.0, window_ms=40)
    blended = blender.blend(signal, sr)

    assert signal.shape == blended.shape

    # Extract STFT using internal method to test exactly what the DSP engine saw
    win_samples = blender._ms_to_samples(blender.window_ms, sr)
    hop = win_samples // 2

    # Analyze input
    frames_in = blender._frame_audio(signal, hop, win_samples)
    win = blender._hann_window(sr)
    spec_in = np.fft.rfft(frames_in * win, axis=1)
    mag_in = np.abs(spec_in)
    phase_in = np.angle(spec_in)

    # Analyze output
    frames_out = blender._frame_audio(blended, hop, win_samples)
    spec_out = np.fft.rfft(frames_out * win, axis=1)
    mag_out = np.abs(spec_out)
    phase_out = np.angle(spec_out)

    # Assert magnitude smoothing reduced high-frequency energy
    assert np.sum(mag_out[:, 50:]) < np.sum(mag_in[:, 50:])

    # Ensure phase is preserved inside the prominent bins
    # Because of overlap-add and windowing the phase of the final reconstructed audio won't be perfectly identical to the theoretical STFT bins
    # However, for bins with actual harmonic content, the phase will be largely preserved.
    # Let's filter to just the prominent bins
    peak_mag = np.max(mag_in)
    mask = mag_in > (peak_mag * 0.1) # top 10% of bins

    phase_diff = np.abs(np.angle(np.exp(1j * (phase_in[mask] - phase_out[mask]))))
    assert np.max(phase_diff) < 0.25

def test_harmonic_blender_stereo():
    sr = 44100
    signal = generate_harmonic_signal(sr)
    signal_stereo = np.column_stack((signal, signal))

    blender = HarmonicBlender(strength=0.5, window_ms=40)
    blended = blender.blend(signal_stereo, sr)

    assert signal_stereo.shape == blended.shape
    assert blended.shape[1] == 2, "Stereo array must have shape (numSamples, 2)"

    win_samples = blender._ms_to_samples(blender.window_ms, sr)
    hop = win_samples // 2
    win = blender._hann_window(sr)

    frames_in = blender._frame_audio(signal_stereo[:, 0], hop, win_samples)
    spec_in = np.fft.rfft(frames_in * win, axis=1)
    mag_in = np.abs(spec_in)
    phase_in = np.angle(spec_in)

    frames_out = blender._frame_audio(blended[:, 0], hop, win_samples)
    spec_out = np.fft.rfft(frames_out * win, axis=1)
    mag_out = np.abs(spec_out)
    phase_out = np.angle(spec_out)

    peak_mag = np.max(mag_in)
    mask = mag_in > (peak_mag * 0.1)
    phase_diff = np.abs(np.angle(np.exp(1j * (phase_in[mask] - phase_out[mask]))))
    assert np.max(phase_diff) < 0.25


def test_harmonic_blender_handles_empty_and_short_audio():
    blender = HarmonicBlender()

    empty = np.array([], dtype=np.float32)
    np.testing.assert_array_equal(blender.blend(empty, 44100), empty)

    short = np.ones(32, dtype=np.float32)
    assert blender.blend(short, 44100).shape == short.shape

    integer_stereo = np.ones((32, 2), dtype=np.int16)
    assert np.issubdtype(blender.blend(integer_stereo, 44100).dtype, np.floating)

def test_harmonic_blender_identity():
    sr = 44100
    duration = 0.5
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Simple sine wave
    audio = np.sin(2 * np.pi * 440 * t)

    blender = HarmonicBlender(strength=0.0)
    audio_out = blender.blend(audio, sr)

    # Assert
    assert np.allclose(audio, audio_out, atol=1e-5)

def test_harmonic_blender_streaming_continuity():
    """When strength is 0, the chunked output should exactly match the full output."""
    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)

    blender_full = HarmonicBlender(strength=0.0)
    out_full = blender_full.blend(audio, sr)

    block_sizes = [32, 64, 128, 256, 512, 1024, 4096]
    for block_size in block_sizes:
        out_chunked = np.zeros_like(audio)
        blender_chunked = HarmonicBlender(strength=0.0)

        for i in range(0, len(audio), block_size):
            chunk = audio[i:i+block_size]
            out_chunked[i:i+len(chunk)] = blender_chunked.blend(chunk, sr)

        diff = np.abs(out_full - out_chunked)
        max_diff = np.max(diff)
        assert max_diff < 1e-4, f"Streaming continuity failed for block size {block_size}. Max diff: {max_diff}"

@pytest.mark.xfail(reason="Streaming continuity lacks retained state across chunks for non-zero strength (Residual Risk #1)")
def test_harmonic_blender_streaming_nonzero_strength():
    """When strength > 0, the lack of overlap-add state retention between chunks causes discontinuities."""
    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)

    blender_full = HarmonicBlender(strength=0.5)
    out_full = blender_full.blend(audio, sr)

    block_size = 512
    out_chunked = np.zeros_like(audio)
    blender_chunked = HarmonicBlender(strength=0.5)

    for i in range(0, len(audio), block_size):
        chunk = audio[i:i+block_size]
        out_chunked[i:i+len(chunk)] = blender_chunked.blend(chunk, sr)

    diff = np.abs(out_full - out_chunked)
    max_diff = np.max(diff)
    assert max_diff < 1e-4, f"Streaming continuity should ideally hold even for non-zero strength. Max diff: {max_diff}"

def test_harmonic_blender_odd_windows():
    sr = 44100
    duration = 0.5
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)

    # 10ms at 44100Hz is 441 samples (odd)
    blender_10 = HarmonicBlender(strength=0.0, window_ms=10)
    out_10 = blender_10.blend(audio, sr)
    assert np.allclose(audio, out_10, atol=1e-5), "Failed identity test with odd window (10ms)"

    # 30ms at 44100Hz is 1323 samples (odd)
    blender_30 = HarmonicBlender(strength=0.0, window_ms=30)
    out_30 = blender_30.blend(audio, sr)
    assert np.allclose(audio, out_30, atol=1e-5), "Failed identity test with odd window (30ms)"
