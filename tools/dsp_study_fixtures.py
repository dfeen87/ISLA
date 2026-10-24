"""Original deterministic sources for the controlled LIVE DSP study.

``fixtures(sr, channels)`` returns a name -> float32 (frames, channels) dict.
Every source lasts six seconds, starts with at least 4096 exact-zero samples,
and ends with at least 4096 exact-zero samples. Source gains are fixed here;
there is no render-dependent peak, RMS, or loudness normalization. The same
array must be passed to every mode with equivalent DSP state initialization.

These are synthesized test signals, not acoustic recordings. In particular,
``solo_piano`` is an additive, mildly inharmonic piano-like model, not a claim
to reproduce a real piano or its perceptual response. Its fast excitation and
frequency-dependent decays exercise attacks and partial-rich decays. Melody,
rhythm, oscillator phases, noise seeds, and pans are original study choices;
no external recording, sample, stream, or quoted musical work is used.

Partial amplitudes are bounded analytically by their coefficient sums. Fixed
gains and a final validation assertion preserve source headroom, including in
dense mixtures. Some noise sources use bounded uniform noise and first
differences (a simple high-pass emphasis), not a model of a real instrument.
No claim about acoustic-instrument listening quality follows from them.

``fixture_manifest`` records provenance, event times, expected probe features,
and source peaks. Event times are absolute seconds in the returned source,
before the LIVE DSP's delay. Musical onset times name excitation starts;
finite attack envelopes mean they need not equal a detector's picked onset.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np


DURATION_SECONDS = 6.0
SEED = 20261024
SOURCE_PEAK_LIMIT = 0.85
FIXTURE_NAMES = (
    "solo_piano",
    "connected_melody",
    "harmonic_sustain",
    "percussion",
    "dense_mix",
    "quiet_dynamic",
    "silence",
    "impulse",
    "sweep",
    "simple_tone",
    "stereo_probe",
)

PROVENANCE = {
    "kind": "original deterministic mathematical synthesis",
    "external_audio": False,
    "recording": False,
    "seed": SEED,
    "notes": (
        "Generated from oscillators, analytic envelopes, and seeded bounded "
        "noise. No external recordings, samples, or music streams are used. "
        "Piano-like and percussion labels describe synthesis test roles."
    ),
}


def _configuration(sr: int, channels: int) -> tuple[int, int]:
    if sr not in (44100, 48000) or channels not in (1, 2):
        raise ValueError("Study fixtures support 44100/48000 Hz, mono/stereo.")
    # 1/8 second is >4096 samples at both supported rates.
    return round(DURATION_SECONDS * sr), max(4096, round(0.125 * sr))


def _time(sr: int, duration: float) -> np.ndarray:
    return np.arange(round(duration * sr), dtype=np.float64) / sr


def _envelope(t: np.ndarray, attack: float, release: float) -> np.ndarray:
    """Raised-cosine attack/release, with exact-zero first and last samples."""
    if len(t) < 2:
        return np.zeros_like(t)
    duration = t[-1]
    attack_phase = np.minimum(t / attack, 1.0)
    release_phase = np.minimum((duration - t) / release, 1.0)
    return (0.5 - 0.5 * np.cos(np.pi * attack_phase)) * (
        0.5 - 0.5 * np.cos(np.pi * release_phase)
    )


def _voice(sr: int, hz: float, duration: float, kind: str) -> np.ndarray:
    t = _time(sr, duration)
    if kind == "piano_like":
        harmonic_count = min(16, int(0.45 * sr / hz))
        partials = np.arange(1, harmonic_count + 1, dtype=np.float64)
        coefficients = partials ** -1.3
        result = np.zeros_like(t)
        for k, a in zip(partials, coefficients / coefficients.sum()):
            frequency = hz * k * np.sqrt(1 + 0.00035 * k * k)
            # Avoid frequencies beyond the spectral test's useful range.
            if frequency >= 0.48 * sr:
                continue
            decay = np.exp(-t * (1.25 + 0.36 * k))
            result += a * decay * np.cos(2 * np.pi * frequency * t)
        return result * _envelope(t, 0.003, 0.045)
    if kind == "legato_tone":
        partials = np.arange(1, min(12, int(0.45 * sr / hz)) + 1)
        coefficients = partials.astype(np.float64) ** -1.5
        result = sum(
            a * np.sin(2 * np.pi * k * hz * t)
            for k, a in zip(partials, coefficients / coefficients.sum())
        )
        return result * _envelope(t, 0.025, 0.10)
    raise ValueError(f"Unknown source voice: {kind}")


def _add(
    target: np.ndarray,
    signal: np.ndarray,
    sr: int,
    start: float,
    gain: float,
    pan: float = 0.0,
) -> None:
    """Add a mono source with equal-power stereo pan (-1 left, +1 right)."""
    offset = round(start * sr)
    if offset < 0 or offset + len(signal) > len(target):
        raise ValueError("Source event extends outside the fixture.")
    if target.shape[1] == 1:
        target[offset : offset + len(signal), 0] += signal * gain
    else:
        angle = (pan + 1) * np.pi / 4
        weights = np.array([np.cos(angle), np.sin(angle)])
        target[offset : offset + len(signal)] += gain * signal[:, None] * weights


def _percussion(sr: int, kind: str, rng: np.random.Generator) -> np.ndarray:
    duration = {"kick": 0.34, "snare": 0.22, "hat": 0.09}[kind]
    t = _time(sr, duration)
    if kind == "kick":
        # The frequency falls from 140 Hz toward 48 Hz. This is intentional.
        phase = 2 * np.pi * (48 * t + 92 * 0.025 * (1 - np.exp(-t / 0.025)))
        return np.sin(phase) * np.exp(-t / 0.075) * _envelope(t, 0.0007, 0.015)
    noise = rng.uniform(-1.0, 1.0, len(t))
    # Difference has absolute amplitude <=1 after division by two.
    high = np.concatenate(([0.0], np.diff(noise) / 2))
    if kind == "snare":
        result = 0.7 * high + 0.3 * np.sin(2 * np.pi * 185 * t)
        return result * np.exp(-t / 0.055) * _envelope(t, 0.0008, 0.012)
    return high * np.exp(-t / 0.018) * _envelope(t, 0.0003, 0.005)


def _build(sr: int, channels: int) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    frames, guard = _configuration(sr, channels)
    origin = guard / sr
    output = {name: np.zeros((frames, channels), np.float64) for name in FIXTURE_NAMES}
    info: dict[str, Any] = {
        name: {"events": [], "description": ""} for name in FIXTURE_NAMES
    }

    def event(name: str, when: float, duration: float, kind: str, **kwargs: Any) -> float:
        start = origin + when
        info[name]["events"].append(
            {"time_seconds": start, "duration_seconds": duration, "kind": kind, **kwargs}
        )
        return start

    piano_events = ((0.12, 261.6256), (1.28, 329.6276), (2.52, 391.9954), (3.68, 293.6648))
    for j, (when, hz) in enumerate(piano_events):
        start = event("solo_piano", when, 1.5, "piano_like", fundamental_hz=hz)
        _add(output["solo_piano"], _voice(sr, hz, 1.5, "piano_like"), sr, start, 0.48, (-1) ** j * 0.25)
    info["solo_piano"]["description"] = "Piano-like additive attacks/decays; mild fixed partial inharmonicity."

    melody = (220.0, 261.6256, 293.6648, 246.9417, 329.6276, 293.6648, 391.9954, 329.6276)
    for j, hz in enumerate(melody):
        start = event("connected_melody", 0.1 + 0.57 * j, 0.68, "overlapping_tone", fundamental_hz=hz)
        _add(output["connected_melody"], _voice(sr, hz, 0.68, "legato_tone"), sr, start, 0.25, 0.2 * np.sin(j))
    info["connected_melody"]["description"] = "Original eight-note sequence; 110 ms overlap of shaped harmonic voices."

    t = _time(sr, 4.9)
    partials = np.arange(1, 33)
    coefficients = 1 / partials.astype(np.float64)
    rich = sum(a * np.sin(2 * np.pi * k * 110 * t) for k, a in zip(partials, coefficients / coefficients.sum()))
    # Shared slow amplitude variation creates no frequency modulation.
    rich *= _envelope(t, 0.08, 0.25) * (0.85 + 0.15 * np.cos(2 * np.pi * 0.6 * t))
    start = event("harmonic_sustain", 0.1, 4.9, "harmonic_sustain", fundamental_hz=110.0, partials=32)
    _add(output["harmonic_sustain"], rich, sr, start, 0.48)
    info["harmonic_sustain"]["description"] = "32 exact harmonics at 110 Hz, 1/k partial amplitudes, gentle amplitude modulation."

    rng = np.random.default_rng(SEED)
    for j in range(10):
        when = 0.12 + 0.49 * j
        kind = "kick" if j % 2 == 0 else "snare"
        hit = _percussion(sr, kind, rng)
        start = event("percussion", when, len(hit) / sr, kind)
        _add(output["percussion"], hit, sr, start, 0.48, 0.0 if kind == "kick" else 0.2)
        hat = _percussion(sr, "hat", rng)
        start = event("percussion", when + 0.23, len(hat) / sr, "hat")
        _add(output["percussion"], hat, sr, start, 0.24, -0.45)
    info["percussion"]["description"] = "Original kick sweeps and seeded noise/tone snare/hat events; no sampled percussion."

    # Linear fixed-gain combinations retain dynamics and make dense input bounded.
    output["dense_mix"] = (
        0.43 * output["solo_piano"]
        + 0.42 * output["connected_melody"]
        + 0.40 * output["harmonic_sustain"]
        + 0.48 * output["percussion"]
    )
    info["dense_mix"]["description"] = "Fixed-gain mixture of the four musical synthetic fixtures."
    info["dense_mix"]["components"] = {"solo_piano": 0.43, "connected_melody": 0.42, "harmonic_sustain": 0.40, "percussion": 0.48}
    info["dense_mix"]["events"] = [
        dict(item, source_fixture=name)
        for name in ("solo_piano", "connected_melody", "harmonic_sustain", "percussion")
        for item in info[name]["events"]
    ]

    for j, gain in enumerate((0.006, 0.018, 0.06, 0.20, 0.46)):
        hz = (220.0, 277.1826, 329.6276, 246.9417, 293.6648)[j]
        start = event("quiet_dynamic", 0.10 + j * 0.94, 0.85, "piano_like", fundamental_hz=hz, fixed_gain=gain)
        _add(output["quiet_dynamic"], _voice(sr, hz, 0.85, "piano_like"), sr, start, gain, (-1) ** j * 0.3)
    info["quiet_dynamic"]["description"] = "Identically shaped piano-like events with fixed gains from 0.006 to 0.46."
    info["silence"]["description"] = "Exact digital zero throughout."

    for j, (when, amplitude) in enumerate(((0.8, 0.5), (2.7, -0.5), (4.5, 0.25))):
        start = event("impulse", when, 1 / sr, "unit_sample", amplitude=amplitude)
        output["impulse"][round(start * sr)] = amplitude
    info["impulse"]["description"] = "Separated positive/negative unit samples, identical in both stereo channels."

    duration = 4.9
    t = _time(sr, duration)
    f0, f1 = 20.0, 0.46 * sr
    chirp = 0.30 * np.sin(2 * np.pi * (f0 * t + (f1 - f0) / (2 * duration) * t * t))
    chirp *= _envelope(t, 0.025, 0.025)
    start = event("sweep", 0.1, duration, "linear_frequency_sweep", frequency_start_hz=f0, frequency_end_hz=f1)
    # Same signal and amplitude per channel, for simple stereo preservation checks.
    offset = round(start * sr)
    output["sweep"][offset : offset + len(chirp)] = chirp[:, None]
    info["sweep"]["description"] = "Linear 20 Hz to 0.46*sample-rate sweep with 25 ms cosine ramps; no pitch stationarity expectation."

    t = _time(sr, 4.9)
    tone = 0.35 * np.sin(2 * np.pi * 440 * t) * _envelope(t, 0.025, 0.025)
    start = event("simple_tone", 0.1, 4.9, "sine", fundamental_hz=440.0)
    offset = round(start * sr)
    output["simple_tone"][offset : offset + len(tone)] = tone[:, None]
    info["simple_tone"]["description"] = "440 Hz sinusoid, identical in both stereo channels, 25 ms cosine ramps."

    t = _time(sr, 4.9)
    env = _envelope(t, 0.025, 0.025)
    common = 0.18 * np.sin(2 * np.pi * 220 * t)
    difference = 0.10 * np.sin(2 * np.pi * 659.2551 * t + 0.6)
    left = (common + difference + 0.08 * np.sin(2 * np.pi * 880 * t)) * env
    right = (common - difference + 0.08 * np.sin(2 * np.pi * 1100 * t + 0.4)) * env
    start = event("stereo_probe", 0.1, 4.9, "stereo_partial_probe", component_hz=[220.0, 659.2551, 880.0, 1100.0])
    offset = round(start * sr)
    if channels == 2:
        output["stereo_probe"][offset : offset + len(t), 0] = left
        output["stereo_probe"][offset : offset + len(t), 1] = right
    else:
        output["stereo_probe"][offset : offset + len(t), 0] = (left + right) / 2
    info["stereo_probe"]["description"] = "Shared 220 Hz, antiphase 659.2551 Hz, channel-specific upper tones; mono is exact stereo fold-down."

    for name in FIXTURE_NAMES:
        source = output[name]
        # Guarantee quiet edges even if future event edits accidentally extend.
        # Fail rather than silently truncate or change synthesis gains.
        if np.any(source[:guard]) or np.any(source[-guard:]):
            raise AssertionError(f"{name}: source event violates the silence guard")
        peak = float(np.max(np.abs(source)))
        if not np.isfinite(source).all() or peak > SOURCE_PEAK_LIMIT:
            raise AssertionError(f"{name}: invalid source headroom, peak={peak}")
        output[name] = source.astype(np.float32)
        info[name].update({"source_peak": float(np.max(np.abs(output[name]))), "frames": frames, "channels": channels})
    return output, info


def fixtures(sr: int, channels: int) -> dict[str, np.ndarray]:
    """Build fresh independent source arrays with fixed deterministic gains."""
    return _build(sr, channels)[0]


def fixture_manifest(sr: int, channels: int) -> dict[str, Any]:
    """Return JSON-serializable provenance, event, and actual source metadata."""
    _, guard = _configuration(sr, channels)
    _, info = _build(sr, channels)
    return {
        "schema_version": 1,
        "provenance": dict(PROVENANCE),
        "samplerate": sr,
        "channels": channels,
        "duration_seconds": DURATION_SECONDS,
        "silence_guard_frames": guard,
        "source_peak_limit": SOURCE_PEAK_LIMIT,
        "normalization": "fixed synthesis gains; no per-render normalization",
        "fixtures": info,
    }


if __name__ == "__main__":
    # Validation/manifest inspection only: importing or executing never opens an
    # audio device, records, monitors, or downloads anything.
    print(json.dumps(fixture_manifest(48000, 2), indent=2))
