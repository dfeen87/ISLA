#!/usr/bin/env python3
"""Reproduce LIVE startup and near-null-bin sensitivity, without audio devices.

This experiment uses the unchanged production StreamingDSP and generated signals.
It characterizes numerical differences; it does not measure perceived quality.

Example (from an installed checkout):
    python tools/dsp_study_edge_cases.py --output edge_cases.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

from isla.streaming import StreamingDSP


SEED = 72
HOP = 512
DELAY = 1536
MODES = ("velvet", "legato", "melt")


def rms(audio):
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))


def relative_difference(actual, reference):
    denominator = rms(reference)
    return rms(actual.astype(np.float64) - reference) / denominator if denominator else None


def peak(audio):
    return float(np.max(np.abs(audio))) if audio.size else 0.0


def stereo_correlation(audio):
    if audio.shape[1] != 2 or not np.any(audio):
        return None
    a, b = audio[:, 0].astype(np.float64), audio[:, 1].astype(np.float64)
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def render(audio, rate, mode, pre_roll=0):
    """Return entire emitted stream, including pre-delay and zero-flush regions."""
    dsp = StreamingDSP(rate, audio.shape[1])
    dsp.select(mode)
    padded = np.pad(audio, ((pre_roll, DELAY + (-len(audio)) % HOP), (0, 0)))
    return np.concatenate([dsp.process_block(padded[index:index + HOP])
                           for index in range(0, len(padded), HOP)])


def stereo_source(mono, channels):
    """Use .6 proportional right channel to expose gain/null sensitivity."""
    if channels == 1:
        return mono[:, None].astype(np.float32)
    return np.stack((mono, np.float32(.6) * mono), axis=1).astype(np.float32)


def startup_cases():
    rows = []
    count = 4096
    for rate in (44100, 48000):
        time = np.arange(count) / rate
        signals = {
            "dc_step_0.5": np.full(count, .5, np.float32),
            "cosine_20_hz_0.5": (.5 * np.cos(2 * np.pi * 20 * time)).astype(np.float32),
            "sine_440_hz_0.5": (.5 * np.sin(2 * np.pi * 440 * time)).astype(np.float32),
            "impulse_0.5": np.pad(np.array([.5], np.float32), (0, count - 1)),
            "silence": np.zeros(count, np.float32),
        }
        for channels in (1, 2):
            for name, mono in signals.items():
                audio = stereo_source(mono, channels)
                for mode in ("bypass",) + MODES:
                    for pre_roll in (0, 8192):
                        output = render(audio, rate, mode, pre_roll)
                        aligned = output[pre_roll + DELAY:pre_roll + DELAY + count]
                        before = output[pre_roll:pre_roll + DELAY]
                        flat_index = int(np.argmax(np.abs(output)))
                        frame_index, channel_index = np.unravel_index(flat_index, output.shape)
                        rows.append({
                            "rate_hz": rate, "channels": channels, "source": name,
                            "mode": mode, "pre_roll_samples": pre_roll,
                            "source_peak": peak(audio), "full_output_peak": peak(output),
                            "output_peak_frame": int(frame_index),
                            "output_peak_channel": int(channel_index),
                            "source_delayed_onset_frame": pre_roll + DELAY,
                            "pre_delayed_onset_peak": peak(before),
                            "pre_delayed_onset_rms": rms(before),
                            "aligned_source_relative_rms_difference": relative_difference(aligned, audio),
                            "samples_abs_gt_1": int(np.count_nonzero(np.abs(output) > 1)),
                            "bypass_bit_exact_after_alignment": bool(np.array_equal(aligned, audio))
                            if mode == "bypass" else None,
                        })
    return rows


def null_and_gain_cases():
    perturbation_rows = []
    gain_rows = []
    count = 65536
    crop = 4096
    for rate in (44100, 48000):
        time = np.arange(count) / rate
        for channels in (1, 2):
            for name, frequency in (
                ("bin_20", 20 * rate / 2048),
                ("bin_40", 40 * rate / 2048),
                ("off_bin_220_hz", 220.0),
                ("off_bin_440_hz", 440.0),
                ("off_bin_1000_hz", 1000.0),
            ):
                mono = (.5 * np.sin(2 * np.pi * frequency * time)).astype(np.float32)
                audio = stereo_source(mono, channels)
                for mode in MODES:
                    reference = render(audio, rate, mode)[DELAY:DELAY + count]
                    reference_crop = reference[crop:-crop]
                    source_crop = audio[crop:-crop]
                    for standard_deviation in (1e-8, 1e-7, 1e-6):
                        noise = np.random.default_rng(SEED).normal(size=audio.shape) * standard_deviation
                        changed = (audio.astype(np.float64) + noise).astype(np.float32)
                        output = render(changed, rate, mode)[DELAY:DELAY + count]
                        output_crop = output[crop:-crop]
                        perturbation_rows.append({
                            "rate_hz": rate, "channels": channels, "source": name,
                            "frequency_hz": frequency, "mode": mode,
                            "gaussian_noise_standard_deviation": standard_deviation,
                            "noise_seed": SEED,
                            "input_relative_rms_change": relative_difference(changed[crop:-crop], source_crop),
                            "output_relative_rms_change": relative_difference(output_crop, reference_crop),
                            "reference_stereo_correlation": stereo_correlation(reference_crop),
                            "perturbed_stereo_correlation": stereo_correlation(output_crop),
                            "reference_peak": peak(reference_crop),
                            "perturbed_peak": peak(output_crop),
                        })
                    for gain in (.5, .0078125, .1, .01):
                        changed = audio * np.float32(gain)
                        output = render(changed, rate, mode)[DELAY:DELAY + count]
                        expected = reference * np.float32(gain)
                        gain_rows.append({
                            "rate_hz": rate, "channels": channels, "source": name,
                            "frequency_hz": frequency, "mode": mode, "gain": gain,
                            "gain_is_exact_power_of_two": gain in (.5, .0078125),
                            "output_relative_rms_scaling_error": relative_difference(
                                output[crop:-crop], expected[crop:-crop]),
                            "output_max_abs_scaling_error": peak(output[crop:-crop] - expected[crop:-crop]),
                            "source_stereo_correlation": stereo_correlation(source_crop),
                            "reference_stereo_correlation": stereo_correlation(reference_crop),
                            "scaled_output_stereo_correlation": stereo_correlation(output[crop:-crop]),
                        })
    return perturbation_rows, gain_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Destination JSON file")
    arguments = parser.parse_args()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    startup = startup_cases()
    perturbation, gain = null_and_gain_cases()
    result = {
        "kind": "ISLA LIVE deterministic edge-case characterization",
        "tested_commit": commit,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "production_dsp_modified": False,
        "audio_devices_opened": False,
        "perceptual_quality_claim": False,
        "definitions": {
            "rms": "sqrt(mean(square(signal))), float64 arithmetic, all channels",
            "relative_rms_change": "RMS(actual-reference) / RMS(reference)",
            "null_and_gain_source_length_samples": 65536,
            "null_and_gain_crop_samples_each_end": 4096,
            "startup_source_length_samples": 4096,
            "stereo_source": "left=mono; right=float32(.6)*mono",
            "dither": "NumPy default_rng(72), independent Gaussian draws per sample/channel",
            "startup_pre_delayed_onset": "emitted [pre_roll, pre_roll+1536), before delayed source onset",
            "startup_full_output": "includes entire emitted pre-delay and flushed source, no discarded samples",
            "note": "Tiny changes near input spectral nulls can alter assigned phases of newly populated bins.",
        },
        "startup": startup,
        "null_bin_perturbation": perturbation,
        "gain_scaling": gain,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {len(startup)} startup, {len(perturbation)} null/dither and "
          f"{len(gain)} scaling measurements to {arguments.output}")


if __name__ == "__main__":
    main()
