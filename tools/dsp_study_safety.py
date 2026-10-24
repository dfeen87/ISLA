"""Research checks of the unchanged LIVE path; never opens an audio device.

Run from any directory: python tools/dsp_study_safety.py --output safety.json
Numerical equality and float32 bit equality are reported separately because
IEEE signed zeros compare equal but have different bit representations.
The array-size check bounds retained DSP arrays, not whole-process memory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isla.streaming import MODES, StreamingDSP


def retained_arrays(dsp):
    return {key: (value.shape, value.dtype.str, value.nbytes)
            for key, value in vars(dsp).items() if isinstance(value, np.ndarray)}


def render(dsp, audio):
    padded = np.pad(audio, ((0, dsp.delay), (0, 0)))
    blocks = [dsp.process_block(padded[i:i + dsp.hop])
              for i in range(0, len(padded), dsp.hop)]
    return np.concatenate(blocks)


def configuration(rate, channels, sustained_blocks):
    rng = np.random.default_rng(20261024 + rate + channels)
    dsp = StreamingDSP(rate, channels)
    audio = rng.uniform(-1.25, 1.25, (32 * dsp.hop, channels)).astype(np.float32)
    # Signed zero, subnormal, and full-scale/exceeding-full-scale finite values.
    edge = np.array([0., -0., np.nextafter(np.float32(0), np.float32(1)),
                     -np.nextafter(np.float32(0), np.float32(1)), 1., -1., 1.25, -1.25], np.float32)
    audio[:len(edge)] = edge[:, None]
    output = render(dsp, audio)
    aligned = output[dsp.delay:]
    assert not np.any(output[:dsp.delay])
    assert np.array_equal(aligned, audio)
    mismatched_bits = aligned.view(np.uint32) != audio.view(np.uint32)
    signed_zero_only = bool(np.all((aligned[mismatched_bits] == 0) & (audio[mismatched_bits] == 0)))
    assert signed_zero_only

    selected = StreamingDSP(rate, channels)
    references = [StreamingDSP(rate, channels) for _ in MODES]
    for reference, mode in zip(references, MODES):
        reference.select(mode)
    initial_arrays = retained_arrays(selected)
    maximum_switch_error = 0.
    old_mode = "bypass"
    state_checks = 0
    for index in range(sustained_blocks):
        # Same continuously generated input for every bank, with periodic silence.
        block = rng.normal(0., .1, (selected.hop, channels)).astype(np.float32)
        if index % 113 < 4:
            block.fill(0.)
        mode = MODES[(index // 7) % len(MODES)] if index < 64 else MODES[index % len(MODES)]
        banks = [reference.process_block(block) for reference in references]
        selected.select(mode)
        actual = selected.process_block(block)
        assert np.isfinite(actual).all()
        expected = (banks[MODES.index(old_mode)] * (1. - selected.fade) +
                    banks[MODES.index(mode)] * selected.fade)
        error = float(np.max(np.abs(actual - expected)))
        maximum_switch_error = max(maximum_switch_error, error)
        np.testing.assert_allclose(actual, expected, atol=1e-7, rtol=0)
        # Selection must leave all warmed spectral histories bit-identical.
        for reference in references:
            for name in ("history", "tails", "weights", "dry"):
                assert np.array_equal(getattr(selected, name), getattr(reference, name))
                state_checks += 1
        assert retained_arrays(selected) == initial_arrays
        old_mode = mode

    contamination_checks = 0
    for mode in MODES:
        clean = StreamingDSP(rate, channels)
        contaminated = StreamingDSP(rate, channels)
        clean.select(mode)
        contaminated.select(mode)
        for index in range(24):
            block = rng.normal(0., .1, (clean.hop, channels)).astype(np.float32)
            other = block.copy()
            if index in (5, 8, 11):
                other[7, 0] = {5: np.nan, 8: np.inf, 11: -np.inf}[index]
                block.fill(0.)
            np.testing.assert_array_equal(clean.process_block(block), contaminated.process_block(other))
            assert all(np.isfinite(value).all() for value in vars(contaminated).values()
                       if isinstance(value, np.ndarray))
            contamination_checks += 1

    silent = StreamingDSP(rate, channels)
    for mode in MODES:
        silent.select(mode)
        for _ in range(8):
            assert not np.any(silent.process_block(np.zeros((silent.hop, channels), np.float32)))

    return dict(rate=rate, channels=channels, delay_frames=dsp.delay,
                delay_ms=1000 * dsp.delay / rate, bypass_exact_numerical=True,
                bypass_bit_mismatch_samples=int(mismatched_bits.sum()),
                bypass_bit_mismatches_signed_zero_only=signed_zero_only,
                bypass_peak_error=float(np.max(np.abs(aligned - audio))),
                input_peak=float(np.max(np.abs(audio))), output_peak=float(np.max(np.abs(aligned))),
                sustained_blocks=sustained_blocks,
                sustained_audio_seconds=sustained_blocks * dsp.hop / rate,
                maximum_switch_reference_error=maximum_switch_error,
                warmed_bank_state_array_equal_checks=state_checks,
                retained_array_bytes=sum(spec[2] for spec in initial_arrays.values()),
                retained_array_layout_stable=True, contamination_checks=contamination_checks,
                nonfinite_policy="Entire hop containing any NaN/Inf is replaced with zeros before retained-state update.",
                silence_exact_zero=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sustained-blocks", type=int, default=2000)
    args = parser.parse_args()
    if args.sustained_blocks < 64:
        parser.error("--sustained-blocks must be at least 64")
    result = dict(kind="deterministic-software-safety-research", python=platform.python_version(),
                  numpy=np.__version__, platform=platform.platform(), seed=20261024,
                  production_dsp_modified=False, audio_device_opened=False,
                  limitations=["No native transport, routing, acoustic, or subjective listening acceptance.",
                               "Retained-array layout is not a process RSS or real-time safety guarantee.",
                               "Switch reference uses independently advanced float32 outputs; absolute tolerance 1e-7."],
                  results=[configuration(rate, channels, args.sustained_blocks)
                           for rate in (44100, 48000) for channels in (1, 2)])
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
