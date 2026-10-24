"""Small post-freeze engineering audit; never reruns the Experiment 02 matrix.

Usage: python -m tools.resonance02.slowdown_successor_audit --output NEW_DIRECTORY
The destination must not exist and must be outside the repository. FLOAT WAVs
and their hashes remain external; the small resulting JSON can accompany review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
import soundfile as sf
from scipy.signal import find_peaks

from . import slowdown as frozen
from . import slowdown_successor as successor
from .slowdown_audit import impulse_audit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(destination: Path):
    destination = destination.resolve()
    repo = Path(__file__).resolve().parents[2]
    if destination == repo or repo in destination.parents:
        raise ValueError("evidence must be outside ordinary repository history")
    destination.mkdir(parents=True, exist_ok=False)
    records, ablations, audio = [], [], []
    for sr in (16000, 44100, 48000):
        x = np.zeros((round(1.4 * sr), 1))
        events = np.round(np.array([.25, .65, 1.05]) * sr).astype(int)
        x[events] = .5
        for ratio in (1.25, 1.50):
            for label, module in (("frozen", frozen), ("successor_01", successor)):
                y, d = module.stretch(x, sr, ratio)
                repeated, repeated_d = module.stretch(x, sr, ratio)
                record = dict(sample_rate=sr, ratio=ratio, implementation=label,
                    **impulse_audit(x, y, sr, ratio, [.25, .65, 1.05]),
                    diagnostics=d, deterministic=bool(np.array_equal(y, repeated) and d == repeated_d))
                records.append(record)
                if sr == 16000:
                    path = destination / f"{label}_{sr}_{ratio:.2f}.wav"
                    sf.write(path, y, sr, subtype="FLOAT")
                    audio.append(dict(path=path.name, sha256=sha(path), frames=len(y), channels=1, sr=sr))
        if sr == 16000:
            for ratio in (1.25, 1.50):
                expected = np.round(events * ratio).astype(int)
                for locking, resets in ((True, True), (False, True), (True, False), (False, False)):
                    y, d = frozen.stretch(x, sr, ratio, identity_phase_locking=locking, transient_resets=resets)
                    peaks, _ = find_peaks(abs(y[:, 0]), distance=round(.1 * sr), prominence=.1 * np.max(abs(y)))
                    frames = np.array(d["transient_reset_frames"])
                    predicted = events + frames * frozen.ANALYSIS_HOP * (ratio - 1) if len(frames) == len(events) else None
                    ablations.append(dict(ratio=ratio, locking=locking, resets=resets,
                        detected_output_samples=peaks.tolist(), expected_output_samples=expected.tolist(),
                        reset_frames=frames.tolist(), reset_center_prediction=None if predicted is None else predicted.tolist()))
    sources = [Path(__file__), Path(frozen.__file__), Path(successor.__file__),
        repo / "tests/test_resonance02_slowdown.py", repo / "tests/test_resonance02_slowdown_successor.py"]
    result = dict(schema=1, status="POST-FREEZE ENGINEERING SUCCESSOR 01; NOT EXPERIMENT 02 RE-EVALUATION",
        frozen_commit="f775995d173689967f76f30a3826403d066c06ce",
        freeze_sha256=sha(repo / "docs/research/phase-governed-resonance-02/FREEZE.json"),
        sources={str(p.relative_to(repo)): sha(p) for p in sources},
        environment=dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__,
                         scipy=scipy.__version__, soundfile=sf.__version__),
        measurement_scope="Three known isolated impulses at .25/.65/1.05 s; unchanged 10 ms and event-count screen. "
            "Spread is the 5%-95% energy interval within +/-50 ms, not a perceptual quality claim. "
            "Output peak detector: distance=.10 s, prominence=.10*maximum; no fitted alignment.",
        original_contract_replay="git show 9cef83b:tests/test_resonance02_slowdown.py copied outside test collection; "
            "18 passed, 2 ordinary timing failures remain. Candidate binding changes no assertions or tolerances.",
        records=records, frozen_ablations=ablations, external_audio=audio,
        limitations=["isolated detector-selected attacks only; detected neighbors <4096 samples are unsupported",
            "missed onsets and sample-energy anchor ambiguity remain", "recorded piano stereo and creator listening unvalidated",
            "analysis-phase reinitialization can perturb simultaneous sustained content", "two synthesis passes for admitted signals; offline only"])
    path = destination / "MEASUREMENTS.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(path)
    for row in records:
        print(row["sample_rate"], row["ratio"], row["implementation"], row["detected_output_samples"],
              "max error ms", row["max_abs_timing_error_ms"], "spread ms",
              [e["local_90pct_energy_spread_ms"] for e in row["event_spreads"]])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    audit(parser.parse_args().output)
