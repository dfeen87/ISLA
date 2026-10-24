"""Independent, offline attack diagnostics; no perceptual or physical-strike truth.

References are supplied event points or original-only envelope-rise candidates.
They are frozen before candidate measurements. Lag, peak-rank disagreement and
energy/shape changes have separate fields; zero lag never clears a rank flip.
The 1 ms lag and 2 dB first-10-ms limits are experimental gates, not JND claims.

Prior art: Duxbury et al. DAFx 2003 (spectral novelty/prediction and peak picking),
Dixon DAFx 2006 (physical/perceptual onset uncertainty), and librosa 0.11 onset
documentation. This uses an original-only slope detector rather than claiming a
complete implementation of those papers or sample-accurate recorded annotations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import correlate, find_peaks, resample_poly

SOURCE_SHA256 = "9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15"
LAG_LIMIT_MS = 1.0
ENERGY_LIMIT_DB = 2.0
SEARCH_S = .025
NOVELTY_FRAME, NOVELTY_HOP = 256, 64


def _audio(value):
    x = np.asarray(value, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or x.shape[1] not in (1, 2) or not np.isfinite(x).all():
        raise ValueError("Expected finite mono/stereo audio with samples first")
    return x


def _envelope(x, sr):
    """Centered 1 ms pooled-power RMS, identical to the historical detector."""
    width = max(1, round(.001 * sr))
    if not len(x):
        return np.empty(0)
    return np.sqrt(np.convolve(np.mean(x*x, axis=1), np.ones(width)/width,
                               mode="full")[(width-1)//2:(width-1)//2+len(x)])


def original_references(x, sr):
    """Up to 12 strongest original-only rises, >=100 ms apart.

    This deliberately retains the historical candidate-selection rule. Points
    locate envelope rises, not necessarily note beginnings or hammer strikes.
    """
    slope = np.diff(_envelope(_audio(x), sr))
    chosen = []
    if slope.max(initial=0) <= 1e-10:
        return []
    for i in np.argsort(slope)[::-1]:
        if slope[i] < .25*slope.max() or len(chosen) >= 12:
            break
        if all(abs(i-j) > .1*sr for j in chosen):
            chosen.append(int(i))
    return [i/sr for i in chosen]


def _novelty(x):
    """Centered 256/64 periodic-Hann, pooled magnitudes, positive spectral flux."""
    padded = np.pad(x, ((NOVELTY_FRAME//2, NOVELTY_FRAME//2), (0, 0)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, NOVELTY_FRAME,
                                                     axis=0)[::NOVELTY_HOP]
    w = .5-.5*np.cos(2*np.pi*np.arange(NOVELTY_FRAME)/NOVELTY_FRAME)
    magnitude = np.sqrt(np.mean(np.abs(np.fft.rfft(frames*w, axis=-1))**2,
                                axis=1))
    flux = np.maximum(np.diff(magnitude, axis=0, prepend=magnitude[:1]), 0).sum(axis=1)
    return np.arange(len(flux))*NOVELTY_HOP, flux


def _rank_peaks(values, lo, hi, sr, count=5):
    if hi <= lo:
        return []
    part = values[lo:hi]
    indices, _ = find_peaks(part, distance=max(1, round(.001*sr)))
    # Keep endpoint maxima too; silently losing a boundary peak hides ambiguity.
    indices = np.unique(np.r_[indices, 0, len(part)-1])
    indices = indices[part[indices] > 0]
    indices = sorted(indices, key=lambda i: (-part[i], i))[:count]
    top = float(part[indices[0]]) if len(indices) else 1.
    return [dict(sample=int(lo+i), seconds=float((lo+i)/sr),
                 value=float(part[i]), fraction_of_top=float(part[i]/top))
            for i in indices]


def _ncc(x, y, reference, sr):
    """Fixed original template, lag-normalized candidate windows, no downmix.

    A positive lag means y is later than x. Correlations sum channel evidence,
    preserving antiphase stereo rather than cancelling it through arithmetic mean.
    Each comparison uses the same template length and subtracts each channel's
    own local mean. Candidate window sums provide exact per-lag normalization.
    """
    lo = max(0, reference-round(.010*sr))
    hi = min(len(x), reference+round(.060*sr))
    radius = round(SEARCH_S*sr)
    minimum, maximum = max(-radius, -lo), min(radius, len(y)-hi)
    if hi-lo < 4 or minimum > maximum:
        return dict(lag_samples=None, lag_ms=None, maximum=None, zero_lag=None,
                    ambiguous=True, peaks=[], boundary=False, template_samples=hi-lo)
    template = x[lo:hi]-x[lo:hi].mean(axis=0)
    search = y[lo+minimum:hi+maximum]
    width = hi-lo
    xenergy = float(np.sum(template*template))
    prefix = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(search, axis=0)])
    prefix2 = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(search*search, axis=0)])
    totals = prefix[width:]-prefix[:-width]
    powers = prefix2[width:]-prefix2[:-width]
    yenergy = np.maximum(np.sum(powers-totals*totals/width, axis=1), 0)
    dots = sum(correlate(search[:, c], template[:, c], mode="valid", method="fft")
               for c in range(x.shape[1]))
    denominator = np.sqrt(xenergy*yenergy)
    valid = denominator > 1e-24
    if xenergy < 1e-24 or not np.any(valid):
        return dict(lag_samples=None, lag_ms=None, maximum=None, zero_lag=None,
                    ambiguous=True, peaks=[], boundary=False, template_samples=width)
    scores = np.full(len(dots), -1.)
    scores[valid] = np.clip(dots[valid]/denominator[valid], -1, 1)
    lags = np.arange(minimum, maximum+1)
    best = int(np.argmax(scores))
    candidates, _ = find_peaks(scores, distance=max(1, round(.001*sr)))
    candidates = sorted(set(candidates.tolist()+[best]), key=lambda i: (-scores[i], abs(lags[i])))[:5]
    peaks = [dict(lag_samples=int(lags[i]), ncc=float(scores[i])) for i in candidates]
    competing = any(abs(lags[i]-lags[best]) > .001*sr and
                    scores[i] >= scores[best]-.01 for i in candidates if i != best)
    return dict(lag_samples=int(lags[best]), lag_ms=float(lags[best]*1000/sr),
                maximum=float(scores[best]), zero_lag=float(scores[-minimum]),
                ambiguous=bool(competing or scores[best] < .90), peaks=peaks,
                boundary=bool(abs(lags[best]) == radius), template_samples=width)


def _energy_gain(a, b):
    before, after = float(np.sum(a*a)), float(np.sum(b*b))
    return (float(10*np.log10(after/before)) if before > 1e-24 and after > 1e-24
            else None)


def _shape_residual(a, b):
    """Residual after diagnostic scalar fitting; actual audio is never leveled."""
    energy = float(np.sum(a*a))
    if energy < 1e-24:
        return None
    gain = float(np.sum(a*b)/energy)
    return float(np.sqrt(np.sum((b-gain*a)**2)/energy))


def assess_attacks(x, y, sr, onsets_seconds=None):
    """Return an auditable dictionary per independent original reference point.

    Supplied times must refer to x and remain fixed for every y. With None,
    original_references(x) is computed before observing candidate features.
    Recorded estimates are never labeled exact physical note-stage annotations.
    """
    x, y = _audio(x), _audio(y)
    if x.shape != y.shape or not isinstance(sr, (int, np.integer)) or sr <= 0:
        raise ValueError("Audio shapes must agree and sampling rate must be a positive integer")
    references = original_references(x, sr) if onsets_seconds is None else list(onsets_seconds)
    if any(not np.isfinite(t) or t < 0 or t >= len(x)/sr for t in references):
        raise ValueError("Reference times must be finite and lie within the original")
    if not references:
        return []
    sx, sy = np.diff(_envelope(x, sr)), np.diff(_envelope(y, sr))
    novel_times, nx = _novelty(x)
    _, ny = _novelty(y)
    radius = round(SEARCH_S*sr)
    rows = []
    for t in references:
        center = round(t*sr)
        lo, hi = max(0, center-radius), min(len(sx), center+radius+1)
        original = _rank_peaks(sx, lo, hi, sr)
        candidate = _rank_peaks(sy, lo, hi, sr)
        shift = ((candidate[0]["sample"]-original[0]["sample"])*1000/sr
                 if original and candidate else None)
        near_equal = any(p["fraction_of_top"] >= .95 and
                         abs(p["sample"]-ranking[0]["sample"]) > .001*sr
                         for ranking in (original, candidate) if ranking
                         for p in ranking[1:])
        rank_flip = bool(original and candidate and abs(shift) > LAG_LIMIT_MS and
                         any(abs(p["sample"]-candidate[0]["sample"]) <= .001*sr
                             for p in original[1:]))
        nindices = np.flatnonzero(abs(novel_times-center) <= radius)
        nref = int(nindices[np.argmax(nx[nindices])]) if len(nindices) and nx[nindices].max() > 0 else None
        nout = int(nindices[np.argmax(ny[nindices])]) if len(nindices) and ny[nindices].max() > 0 else None
        nshift = ((novel_times[nout]-novel_times[nref])*1000/sr
                  if nref is not None and nout is not None else None)
        correlation = _ncc(x, y, center, sr)
        end = min(len(x), center+round(.010*sr))
        gain = _energy_gain(x[center:end], y[center:end])
        shape = _shape_residual(x[lo:hi], y[lo:hi])
        labels = []
        if correlation["lag_ms"] is None or correlation["ambiguous"] or correlation["boundary"]:
            labels.append("waveform_lag_ambiguous")
        elif abs(correlation["lag_ms"]) > LAG_LIMIT_MS:
            labels.append("waveform_displacement")
        if near_equal or rank_flip:
            labels.append("competing_peak_ambiguity")
        if ((shift is not None and abs(shift) > LAG_LIMIT_MS) or
                (nshift is not None and abs(nshift) > LAG_LIMIT_MS)):
            labels.append("detector_disagreement")
        if gain is not None and abs(gain) > ENERGY_LIMIT_DB:
            labels.append("attack_energy_change")
        # A measured shape difference says nothing about audibility or preference.
        if shape is not None and shape > 1e-6:
            labels.append("measured_character_difference")
        unresolved = bool(any(label in labels for label in
                              ("waveform_lag_ambiguous", "competing_peak_ambiguity", "detector_disagreement")))
        rows.append(dict(reference_seconds=float(t), reference_sample=center,
            reference_kind=("original_envelope_rise_estimate" if onsets_seconds is None
                            else "supplied_independent_event_point"),
            physical_strike_truth=False,
            waveform_lag_samples=correlation["lag_samples"], waveform_lag_ms=correlation["lag_ms"],
            waveform_ncc=correlation, slope_peak_shift_ms=shift,
            original_slope_peaks=original, candidate_slope_peaks=candidate,
            competing_peak_ambiguity=bool(near_equal or rank_flip), peak_rank_flip=rank_flip,
            novelty_frame=NOVELTY_FRAME, novelty_hop=NOVELTY_HOP,
            novelty_reference_seconds=(float(novel_times[nref]/sr) if nref is not None else None),
            novelty_candidate_seconds=(float(novel_times[nout]/sr) if nout is not None else None),
            novelty_peak_shift_ms=nshift,
            first_10ms_energy_gain_db=gain, zero_lag_gain_fitted_shape_residual=shape,
            labels=labels or ["same_within_measurement"], unresolved=unresolved,
            timing_gate=("UNRESOLVED" if correlation["lag_ms"] is None or correlation["ambiguous"] or
                         correlation["boundary"] else "PASS" if abs(correlation["lag_ms"]) <= LAG_LIMIT_MS else "FAIL"),
            energy_gate=("UNRESOLVED" if gain is None else "PASS" if abs(gain) <= ENERGY_LIMIT_DB else "FAIL"),
            listening_status="PENDING"))
    return rows


def _array_hash(x):
    return hashlib.sha256(np.asarray(x, dtype="<f4").tobytes()).hexdigest()


def investigate(source_path, measurements_path, output_path):
    """Reproduce every preserved recorded failure, preserving the old verdicts."""
    import soundfile as sf
    from .legacy01 import render

    source_path, measurements_path, output_path = map(Path, (source_path, measurements_path, output_path))
    actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if actual_sha != SOURCE_SHA256:
        raise ValueError("Recorded source SHA-256 does not match preserved Experiment 01 source")
    source, native = sf.read(source_path, always_2d=True)
    if native != 44100 or source.shape != (705600, 2):
        raise ValueError("Unexpected pinned source format")
    legacy = json.loads(measurements_path.read_text())
    failures = [r for r in legacy["candidates"] if r["screen_failures"]]
    if len(failures) != 6:
        raise ValueError("Expected the six preserved recorded failure cells; inspect the provided evidence")
    output_path.mkdir(parents=True, exist_ok=False)
    results, table = [], []
    for record in failures:
        sr, channels, mode, amount = (record[k] for k in ("rate", "channels", "profile", "amount"))
        x = source[2*native:8*native]
        if sr != native:
            x = resample_poly(x, sr//np.gcd(sr, native), native//np.gcd(sr, native), axis=0)
        if channels == 1:
            x = x.mean(axis=1, keepdims=True)
        x = np.pad(x, ((round(.125*sr), round(.125*sr)), (0, 0))).astype(np.float32)
        original, _ = render(x, sr, mode)
        candidate, _ = render(x, sr, mode, {mode: amount})
        candidate_hash = _array_hash(candidate)
        original_record = next(r for r in legacy["baselines"] if
                               r["rate"] == sr and r["channels"] == channels and r["mode"] == mode)
        # Original-only references reproduce the old detector exactly; independent
        # source points also remain common across modes for a separate assessment.
        old_references = original_references(original, sr)
        old_rows = assess_attacks(original, candidate, sr, old_references)
        new_slope = np.diff(_envelope(candidate, sr))
        radius = round(.025*sr)
        old_offsets = []
        for t in old_references:
            i = round(t*sr)
            low, high = max(0, i-radius), min(len(new_slope), i+radius+1)
            old_offsets.append((low+int(np.argmax(new_slope[low:high]))-i)*1000/sr)
        expected_offsets = record["versus_original"]["onset_offsets_ms"]
        source_references = original_references(x, sr)
        source_rows = assess_attacks(original, candidate, sr, source_references)
        item = dict(rate=sr, channels=channels, profile=mode, amount=amount,
            preserved_record=record, original_output_sha256=_array_hash(original),
            original_hash_matches=_array_hash(original) == original_record["float32_le_sha256"],
            candidate_output_sha256=candidate_hash,
            candidate_hash_matches=candidate_hash == record["float32_le_sha256"],
            historical_offsets_ms=old_offsets,
            historical_offsets_match=bool(np.allclose(old_offsets, expected_offsets, rtol=0, atol=1e-10)),
            historical_screen_failure_preserved=True,
            historical_reference_assessments=old_rows, common_source_reference_assessments=source_rows,
            conclusion="Original failed screen remains failed; independent diagnostics do not override it; listening pending")
        results.append(item)
        # One row per originally discrepant event, plus the complete JSON above.
        for index, (old, row) in enumerate(zip(old_offsets, old_rows)):
            if abs(expected_offsets[index]) > LAG_LIMIT_MS:
                table.append(dict(rate=sr, channels=channels, profile=mode, amount=amount,
                    original_event_index=index, reference_seconds=row["reference_seconds"],
                    preserved_shift_ms=expected_offsets[index], reproduced_shift_ms=old,
                    waveform_lag_ms=row["waveform_lag_ms"], ncc=row["waveform_ncc"]["maximum"],
                    first_10ms_energy_gain_db=row["first_10ms_energy_gain_db"],
                    slope_shift_ms=row["slope_peak_shift_ms"], novelty_shift_ms=row["novelty_peak_shift_ms"],
                    competing_peak_ambiguity=row["competing_peak_ambiguity"],
                    unresolved=row["unresolved"], labels=";".join(row["labels"]),
                    original_screen="FAIL_PRESERVED", listening_status="PENDING"))
    report = dict(schema_version=1, source_sha256=actual_sha,
        legacy_measurements_sha256=hashlib.sha256(measurements_path.read_bytes()).hexdigest(),
        thresholds=dict(lag_limit_ms=LAG_LIMIT_MS, first_10ms_gain_limit_db=ENERGY_LIMIT_DB,
                        search_ms=25, near_equal_slope_fraction=.95, ncc_competition_delta=.01),
        reference_statement="Original-only envelope-rise estimates; no independent physical strike annotations",
        original_failure_count=len(failures), results=results, failure_event_table=table,
        listening_status="PENDING", thresholds_changed_after_results=False)
    (output_path/"attack-investigation.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    with (output_path/"preserved-failure-table.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]) if table else ["original_screen"])
        writer.writeheader()
        writer.writerows(table)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True,
                        help="Preserved Experiment 01 recorded-measurements.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = investigate(args.source, args.measurements, args.output)
    print(json.dumps(dict(cells=result["original_failure_count"],
        all_hashes_match=all(r["original_hash_matches"] and r["candidate_hash_matches"] for r in result["results"]),
        all_offsets_match=all(r["historical_offsets_match"] for r in result["results"]),
        output=str(args.output)), indent=2))


if __name__ == "__main__":
    main()
