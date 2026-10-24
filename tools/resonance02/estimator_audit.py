"""POST-FREEZE exploratory original-signal estimator diagnostics, no retuning.

Measure frozen core onset evidence against librosa's conventional onset detector.
Synthetic source events permit timing-window comparisons. Recorded piano has no
physical strike annotations; detector agreement must not be called accuracy.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform

import librosa
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.signal import find_peaks
import scipy
import soundfile as sf

from tools.resonance02 import core


REPO = Path(__file__).resolve().parents[2]
TOLERANCE_S = 0.025
DEFINITIONS = {
    "status": "POST-FREEZE exploratory supplementary diagnostic; original signals only; no frozen estimator/threshold changed",
    "our_detector": "Frozen core.analyze feature6 (attack evidence, not normalized attack regime weight); scipy.signal.find_peaks height>=0.5, distance=ceil(0.050*sr/512) frames. Plateau peaks use scipy's middle sample. Only core frame-center times in [0,input duration) are retained; no empirical time correction.",
    "core_frame_times": "(frame_index*hop-frame+hop+frame/2)/sr, exactly the frozen core time vector. N=2048/H=512 frames include complete offline support; timestamps are analysis frame centers, not physical strike claims.",
    "reference_strength": "librosa 1.0.0 onset_strength: N=2048/H=512, lag=1, max_size=1 (frequency max filtering disabled), detrend=False, center=True; default log-power Mel feature and mean frequency aggregation. Compute per-channel envelopes then average channel envelopes; never waveform-downmix stereo.",
    "reference_picking": "librosa.onset.onset_detect on that envelope: normalize=True, backtrack=False, sparse=True, units=time; explicit installed defaults pre_max=floor(0.03*sr/H), post_max=1, pre_avg=floor(0.10*sr/H), post_avg=floor(0.10*sr/H)+1, wait=floor(0.03*sr/H), delta=0.07. Library frame times are index*H/sr with its documented centered-strength compensation; no added N/2 offset.",
    "matching": "One-to-one maximum-cardinality matches with absolute timing difference<=25 ms; minimize total absolute error among those matches. Unmatched detections are false positives only for synthetic ground truth; unmatched known synthetic events are false negatives. Precision=matches/detections; recall=matches/events. Empty denominator gives null. Signed error=detected-reference, so positive means later.",
    "recorded_scope": "The two crops have no physical hammer-strike ground truth. Report only counts and one-to-one detector agreement within 25 ms; reference-matched fractions are agreement, never precision/recall accuracy. No listening or note-stage identification is inferred.",
    "proxy_frames": "Descriptive medians and 10th/90th percentiles on frozen non-silent frames (feature8==0), also subset with any frozen reliable bin. Features: C=3, phase prediction weighted absolute error radians=9, flatness=1-feature2, confidence=5. Reliability is frozen core's current/previous magnitude gate, not a three-frame proof.",
    "proxy_limits": "Flatness is an inexpensive spectral-structure proxy, not stable pitch or harmonic correctness. C is bin-phase predictability, not musical-state truth. A high tonal score or C on percussion/close beating does not validate note labels. Reused synthetic cells/formats are correlated observations, not independent recordings.",
    "scope": "All 4 sample-rate/channel formats for solo_piano, connected_melody, percussion and each recorded crop; proxy stats additionally simple_tone/dense_mix all 4 and 0.2 Hz beating steady/damped 48 kHz mono. No candidate signal was generated or rerendered.",
    "source_references": [
        "https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_strength.html",
        "https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_detect.html",
    ],
    "reference_version_note": "Official 0.11.0 API pages are the references already cited in frozen UFO_PRIOR_ART.md and were checked for these documented semantics. Execution uses installed 1.0.0; the installed onset module source file is hash recorded. This is the default spectral-flux comparator, not the max-filtered SuperFlux configuration.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def our_events(analysis, sr, duration):
    indices, _ = find_peaks(analysis["features"][:, 6], height=0.5,
                            distance=max(1, int(np.ceil(0.050 * sr / 512))))
    times = analysis["time"][indices]
    return times[(times >= 0) & (times < duration)]


def reference_events(x, sr):
    per_channel = librosa.onset.onset_strength(y=x.T, sr=sr, hop_length=512,
        n_fft=2048, lag=1, max_size=1, detrend=False, center=True)
    envelope = np.mean(np.atleast_2d(per_channel), axis=0)
    picking = {"pre_max": int(0.03 * sr // 512), "post_max": 1,
               "pre_avg": int(0.10 * sr // 512), "post_avg": int(0.10 * sr // 512) + 1,
               "wait": int(0.03 * sr // 512), "delta": 0.07}
    detected = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr,
        hop_length=512, backtrack=False, normalize=True, sparse=True,
        units="time", **picking)
    return detected, picking


def matching(detected, expected, synthetic):
    detected, expected = np.asarray(detected), np.asarray(expected)
    matches = []
    if len(detected) and len(expected):
        distance = abs(detected[:, None] - expected[None, :])
        cost = np.where(distance <= TOLERANCE_S, distance, 1e6)
        di, ei = linear_sum_assignment(cost)
        for d, e in zip(di, ei):
            if distance[d, e] <= TOLERANCE_S:
                matches.append({"detected_seconds": float(detected[d]),
                                "reference_seconds": float(expected[e]),
                                "signed_error_ms": float((detected[d] - expected[e]) * 1000)})
    signed = [m["signed_error_ms"] for m in matches]
    result = {"matches": matches, "matched_count": len(matches),
              "detected_count": len(detected), "reference_count": len(expected),
              "unmatched_detections": len(detected) - len(matches),
              "unmatched_references": len(expected) - len(matches),
              "mean_signed_error_ms": float(np.mean(signed)) if signed else None,
              "median_signed_error_ms": float(np.median(signed)) if signed else None,
              "p95_absolute_error_ms": float(np.percentile(np.abs(signed), 95)) if signed else None}
    if synthetic:
        precision = len(matches) / len(detected) if len(detected) else None
        recall = len(matches) / len(expected) if len(expected) else None
        f1 = None if precision is None or recall is None else (2 * precision * recall / (precision + recall) if precision + recall else 0.0)
        result.update(precision=precision, recall=recall, f1=f1)
    else:
        result.update(matched_fraction_of_our_detections=len(matches) / len(detected) if len(detected) else None,
                      matched_fraction_of_reference_detections=len(matches) / len(expected) if len(expected) else None,
                      scope="detector agreement; not physical-onset accuracy")
    return result


def distribution(values):
    values = np.asarray(values)
    if not len(values):
        return {"count": 0, "median": None, "p10": None, "p90": None}
    return {"count": len(values), "median": float(np.median(values)),
            "p10": float(np.percentile(values, 10)), "p90": float(np.percentile(values, 90))}


def proxy_summary(analysis):
    features = analysis["features"]
    active = features[:, 8] == 0
    reliable = active & np.any(analysis["reliable"], axis=(1, 2))
    result = {"total_frames": len(features), "active_frames": int(active.sum()),
              "active_with_any_reliable_bin_frames": int(reliable.sum())}
    for key, mask in (("all_non_silent", active), ("non_silent_any_reliable_bin", reliable)):
        result[key] = {"C": distribution(features[mask, 3]),
                       "phase_error_rad": distribution(features[mask, 9]),
                       "flatness": distribution(1 - features[mask, 2]),
                       "confidence": distribution(features[mask, 5])}
    return result


def run(root):
    root = Path(root).resolve()
    freeze = json.loads((root / "FREEZE.json").read_text())
    manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text())
    assert sha(root / "SOURCE_MANIFEST.json") == freeze["source_manifest_sha256"]
    for path, digest in freeze["code_and_protocol"].items():
        assert sha(REPO / path) == digest, f"Frozen file changed: {path}"
    assert asdict(core.Config()) == freeze["config"]
    onset_names = {"solo_piano", "connected_melody", "percussion", "recorded_piano", "recorded_piano_reserved"}
    proxy_names = {"simple_tone", "percussion", "dense_mix", "beat_440_0.2_steady", "beat_440_0.2_damped"}
    onset_records, proxy_records, verified_paths = [], [], []
    for cell in manifest["cells"]:
        name = cell["name"]
        if name not in onset_names | proxy_names:
            continue
        path = root / cell["path"]
        assert sha(path) == cell["sha256"], f"Source hash mismatch: {path}"
        x, sr = sf.read(path, dtype="float64", always_2d=True)
        assert sr == cell["sr"] and x.shape == (cell["frames"], cell["channels"])
        verified_paths.append(cell["path"])
        analysis = core.analyze(x, sr)
        ours = our_events(analysis, sr, len(x) / sr)
        common = {"source": name, "sr": sr, "channels": cell["channels"],
                  "source_path": cell["path"], "sha256": cell["sha256"]}
        if name in onset_names:
            conventional, settings = reference_events(x, sr)
            row = dict(common, our_event_seconds=ours.tolist(),
                       librosa_event_seconds=conventional.tolist(), librosa_peak_pick_parameters=settings)
            if name.startswith("recorded_"):
                row["detector_agreement"] = matching(ours, conventional, synthetic=False)
                row["ground_truth"] = "ABSENT: no physical strike annotations"
            else:
                known = cell["events_seconds"]
                row.update(known_event_seconds=known,
                    our_synthetic_accuracy=matching(ours, known, synthetic=True),
                    librosa_synthetic_accuracy=matching(conventional, known, synthetic=True))
            onset_records.append(row)
        if name in proxy_names:
            proxy_records.append(dict(common, proxy=proxy_summary(analysis),
                                      attack_evidence_peak_count=len(ours), attack_evidence_peak_seconds=ours.tolist()))
        print("Estimator audit", name, sr, cell["channels"], flush=True)
    installed_path = Path(librosa.onset.__file__)
    result = {"schema": 1, "status": DEFINITIONS["status"], "definitions": DEFINITIONS,
              "freeze_sha256": sha(root / "FREEZE.json"),
              "manifest_sha256": sha(root / "SOURCE_MANIFEST.json"),
              "audit_script_sha256": sha(__file__), "librosa_onset_module_sha256": sha(installed_path),
              "frozen_files_verified": len(freeze["code_and_protocol"]),
              "source_files_verified": len(verified_paths), "source_paths": verified_paths,
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "librosa": librosa.__version__},
              "onset_records": onset_records, "proxy_records": proxy_records,
              "decision": "Exploratory descriptive evidence; no musical-state truth, candidate acceptance or benefit inferred"}
    (root / "ESTIMATOR_AUDIT.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    report(root / "ESTIMATOR_AUDIT.md", result)
    return result


def number(value, pattern=".3f"):
    return format(value, pattern) if value is not None else "n/a"


def report(path, result):
    lines = ["# Original-signal estimator audit", "", "**POST-FREEZE exploratory supplementary diagnostic. No estimator or threshold was retuned.**", "",
        f"Verified {result['source_files_verified']} source files and {result['frozen_files_verified']} frozen code/protocol files. This audit generated no candidate audio.", "",
        "## Synthetic event comparison at 25 ms", "", "|Source|Rate/channels|Detector|Events|Precision|Recall|Mean signed error ms|", "|---|---|---|---|---|---|---|"]
    for row in result["onset_records"]:
        if "known_event_seconds" in row:
            for label, key in (("Frozen core", "our_synthetic_accuracy"), ("librosa", "librosa_synthetic_accuracy")):
                m = row[key]
                lines.append(f"|{row['source']}|{row['sr']}/{row['channels']}|{label}|{m['detected_count']}/{m['reference_count']}|{number(m['precision'])}|{number(m['recall'])}|{number(m['mean_signed_error_ms'])}|")
    lines += ["", "Signed errors include matched events only; unmatched events are reported in the JSON. The 25 ms matching window is a detector-comparison convention, not an acceptable processing-delay tolerance. A perfect synthetic score would not establish physical strike detection on recordings.", "",
        "## Recorded piano: detector agreement only", "", "|Source|Rate/channels|Core/librosa counts|Matched within 25 ms|Core-minus-librosa mean ms|", "|---|---|---|---|---|"]
    for row in result["onset_records"]:
        if "detector_agreement" in row:
            m = row["detector_agreement"]
            lines.append(f"|{row['source']}|{row['sr']}/{row['channels']}|{m['detected_count']}/{m['reference_count']}|{m['matched_count']}|{number(m['mean_signed_error_ms'])}|")
    lines += ["", "No physical-strike annotation exists for these crops. Agreement and disagreement characterize detector behavior; neither detector is assumed to supply ground truth.", "",
        "## Proxy limitations on original signals", "", "|Source|Rate/channels|Median C|Median abs phase error rad|Median flatness|Attack-evidence peaks|", "|---|---|---|---|---|---|"]
    for row in result["proxy_records"]:
        m = row["proxy"]["non_silent_any_reliable_bin"]
        lines.append(f"|{row['source']}|{row['sr']}/{row['channels']}|{number(m['C']['median'],'.6f')}|{number(m['phase_error_rad']['median'],'.6f')}|{number(m['flatness']['median'],'.8f')}|{row['attack_evidence_peak_count']}|")
    lines += ["", "Each 0.2 Hz beating fixture has one registered excitation yet produces six attack-evidence peaks: the initial excitation, four interior peaks near 2.635, 7.637, 12.640 and 17.643 s following beat minima, and an ending-related peak at 20.117 s (the source cuts off at 20.125 s). The interior events show that changes from beating can activate the frozen detector; the ending is a separate boundary artifact. High C and low flatness do not resolve that ambiguity. Percussion also has median C near 0.9 and a high 1-flatness score, so those proxies are not exclusive to stable pitched sustain.", "",
        "These proxies describe spectral structure and predictable bin-phase motion. They do not identify real note stages. Full non-silent and reliable-subset distributions, counts and source hashes are in ESTIMATOR_AUDIT.json.", "", "## Definitions and references", ""]
    for key, definition in DEFINITIONS.items():
        if key != "source_references":
            lines.append(f"- **{key}:** {definition}")
    lines += ["", "The official [onset-strength reference](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_strength.html) documents the log-Mel spectral-flux default and max_size=1 disabling frequency max filtering. The official [onset-detection reference](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_detect.html) documents normalized peak picking and optional backtracking. These are the same primary API sources cited in the frozen U.F.O./DSP prior-art report; execution is pinned to installed librosa 1.0.0 and its onset-module hash.", ""]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
