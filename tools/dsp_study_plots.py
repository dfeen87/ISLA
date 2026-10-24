"""Reproducible figures from the LIVE study's measurements.json.

Usage:
    python tools/dsp_study_plots.py --input <measurements.json or directory> \
        --output <figure directory>

Only consumes already computed measurements; never generates measurements,
captures audio, opens devices, or modifies DSP. Writes paired PNG/SVG figures.
RMS matching is explicitly not LUFS matching. Numerical differences describe
the original synthetic sources and are not perceptual-quality scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np


MODES = ("velvet", "legato", "melt")
MODE_LABELS = ("Velvet", "Legato", "Melt")
COLORS = ("#0072B2", "#D55E00", "#009E73")
FIXTURE_ORDER = (
    "solo_piano", "connected_melody", "harmonic_sustain", "percussion",
    "dense_mix", "quiet_dynamic", "simple_tone", "sweep", "impulse",
    "stereo_probe", "silence",
)
FOOTNOTE = (
    "Original deterministic synthetic sources; piano-like is synthesis, not an acoustic recording.\n"
    "Identical delay-aligned inputs. RMS matching is not LUFS matching. Numerical difference is not a quality score."
)


def number(value) -> float:
    return np.nan if value is None else float(value)


def save(fig, output: Path, name: str, footnote: str | None = None) -> None:
    if footnote is None:
        footnote = FOOTNOTE
    fig.text(0.01, 0.005, footnote, ha="left", va="bottom", fontsize=8, color="#404040")
    for suffix in ("png", "svg"):
        fig.savefig(output / f"{name}.{suffix}", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def records_48_stereo(data):
    records = [r for r in data["measurements"] if r["rate"] == 48000 and r["channels"] == 2]
    lookup = {(r["fixture"], r["mode"]): r for r in records}
    names = [n for n in FIXTURE_ORDER if (n, "bypass") in lookup]
    names.extend(n for n, mode in lookup if mode == "bypass" and n not in names)
    return lookup, names


def raw_and_matched(data, output):
    lookup, names = records_48_stereo(data)
    # Silence has zero reference RMS, making the ratio undefined. Keep this
    # mathematical distinction explicit instead of plotting it as zero error.
    names = [n for n in names if any(np.isfinite(number(lookup[n, m].get("relative_rms"))) for m in MODES)]
    if not names:
        return
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    width = 0.24
    x = np.arange(len(names))
    for ax, key, title in zip(
        axes,
        ("relative_rms", "matched_relative_rms"),
        ("Unaltered output versus Bypass", "Output RMS matched to Bypass"),
    ):
        for j, (mode, label, color) in enumerate(zip(MODES, MODE_LABELS, COLORS)):
            vals = [100 * number(lookup[n, mode].get(key)) for n in names]
            ax.bar(x + (j - 1) * width, vals, width, label=label, color=color)
        ax.set_title(title)
        ax.set_xticks(x, names, rotation=60, ha="right")
        ax.set_ylabel("RMS(output − Bypass) / RMS(Bypass) (%)")
        ax.yaxis.set_major_formatter(PercentFormatter(100))
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
    axes[0].legend(frameon=False, ncol=3)
    fig.suptitle("LIVE baseline mode differences · 48 kHz stereo", fontsize=15)
    fig.subplots_adjust(bottom=0.32, top=0.84, wspace=0.12)
    save(fig, output, "01_raw_and_rms_matched", FOOTNOTE + "\nSilence omitted: its zero reference RMS makes relative RMS undefined.")


def heatmap(ax, values, rows, columns, title, unit, signed=False, decimals=2):
    matrix = np.asarray(values, float)
    finite = matrix[np.isfinite(matrix)]
    maximum = float(np.max(np.abs(finite))) if finite.size else 1.0
    maximum = max(maximum, 1e-9)
    cmap = plt.get_cmap("coolwarm" if signed else "YlGnBu").copy()
    cmap.set_bad("#eeeeee")
    image = ax.imshow(np.ma.masked_invalid(matrix), aspect="auto", cmap=cmap,
                      vmin=-maximum if signed else 0, vmax=maximum)
    ax.set_xticks(np.arange(len(columns)), columns)
    ax.set_yticks(np.arange(len(rows)), rows)
    ax.set_title(title, pad=12)
    for (i, j), value in np.ndenumerate(matrix):
        label = f"{value:.{decimals}f}" if np.isfinite(value) else "—"
        color = "white" if np.isfinite(value) and abs(value) > 0.60 * maximum else "#222222"
        ax.text(j, i, label, ha="center", va="center", color=color, fontsize=8)
    plt.colorbar(image, ax=ax, fraction=0.045, pad=0.04, label=unit)


def pairwise(data, output):
    _, names = records_48_stereo(data)
    pairs = (("velvet", "legato"), ("velvet", "melt"), ("legato", "melt"))
    lookup = {
        (r["fixture"], r["a"], r["b"]): r
        for r in data["pairwise"] if r["rate"] == 48000 and r["channels"] == 2
    }
    names = [n for n in names if n != "silence"]
    matrix = [[100 * number(lookup.get((n, a, b), {}).get("rms_matched_relative_rms"))
               for a, b in pairs] for n in names]
    if not names:
        return
    fig, ax = plt.subplots(figsize=(9, 6))
    columns = [f"{a.title()} → {b.title()}\nreference: {b.title()}" for a, b in pairs]
    heatmap(ax, matrix, names, columns,
            "Wet-mode separation after RMS matching · 48 kHz stereo",
            "RMS(matched first mode − reference) / RMS(reference) (%)")
    fig.subplots_adjust(bottom=0.14, top=0.88, left=0.23, right=0.91)
    save(fig, output, "02_pairwise_rms_matched")


def frequency_sensitivity(data, output):
    records = data.get("diagnostics", {}).get("frequency_sensitivity", [])
    if not records:
        return
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex="col")
    for column, rate in enumerate((44100, 48000)):
        for harmonics, color in ((1, "#0072B2"), (8, "#D55E00")):
            subset = sorted((r for r in records if r["rate"] == rate and r["harmonics"] == harmonics), key=lambda r: r["hz"])
            if not subset:
                continue
            x = [r["hz"] for r in subset]
            label = "1 partial" if harmonics == 1 else "up to 8 partials"
            axes[0, column].plot(x, [100 * number(r["relative_rms"]) for r in subset],
                                 "o-", color=color, label=f"{label}, raw")
            axes[0, column].plot(x, [100 * number(r["matched_relative_rms"]) for r in subset],
                                 "s--", color=color, label=f"{label}, RMS matched")
            axes[1, column].plot(x, [number(r["gain_db"]) for r in subset], "o-", color=color, label=label)
        axes[0, column].set_title(f"Melt · {rate:,} Hz mono")
        axes[0, column].set_ylabel("RMS difference / input RMS (%)")
        axes[0, column].yaxis.set_major_formatter(PercentFormatter(100))
        axes[0, column].legend(frameon=False, fontsize=8)
        axes[1, column].set_ylabel("20 log₁₀(output RMS / input RMS) (dB)")
        axes[1, column].set_xlabel("Nominal fundamental frequency (Hz)")
        axes[1, column].axhline(0, color="#555555", lw=0.7)
        for row in range(2):
            axes[row, column].set_xscale("log")
            axes[row, column].grid(alpha=0.2)
    fig.suptitle("Frequency and harmonic-complexity sensitivity · unchanged LIVE kernel", fontsize=15)
    fig.subplots_adjust(bottom=0.16, top=0.88, hspace=0.18, wspace=0.25)
    save(fig, output, "03_frequency_sensitivity", FOOTNOTE + "\nHarmonics above Nyquist are omitted; nominal eight-partial probes contain fewer partials at high fundamentals.")


def cold_start(data, output):
    records = data.get("diagnostics", {}).get("cold_start", [])
    if not records:
        return
    modes = ("bypass",) + MODES
    colors = ("#777777",) + COLORS
    signals = ("dc_step", "impulse", "sine_440")
    labels = ("DC step", "sample-zero impulse", "440 Hz sine")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)
    lookup = {(r["rate"], r["channels"], r["signal"], r["mode"]): r for r in records}
    width = 0.19
    x = np.arange(len(signals))
    for column, rate in enumerate((44100, 48000)):
        for row, channels in enumerate((1, 2)):
            ax = axes[row, column]
            for j, (mode, color) in enumerate(zip(modes, colors)):
                vals = [number(lookup.get((rate, channels, signal, mode), {}).get("raw_peak")) for signal in signals]
                bars = ax.bar(x + (j - 1.5) * width, vals, width, color=color, label=mode.title())
                for bar, value in zip(bars, vals):
                    if np.isfinite(value) and value > 0:
                        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.12, f"{value:.3g}",
                                rotation=90, ha="center", va="bottom", fontsize=7)
            ax.axhline(1, color="#B00020", lw=1.2, linestyle="--", label="1.0 full scale")
            ax.set_yscale("log")
            ax.set_ylim(bottom=0.1)
            ax.set_xticks(x, labels)
            ax.set_title(f"{rate:,} Hz · {channels} channel{'s' if channels > 1 else ''}")
            ax.set_ylabel("Peak absolute raw sample (log scale)")
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
    axes[0, 0].legend(frameon=False, fontsize=8, ncol=3)
    fig.suptitle("Cold-start probes · nominal input peak 0.5 · no silence pre-roll", fontsize=15)
    fig.subplots_adjust(bottom=0.15, top=0.87, hspace=0.28, wspace=0.16)
    save(fig, output, "04_cold_start_peaks",
         "Raw output includes all samples before and after the 1536-frame delay; mode selected before the first block.\n"
         "Input DC/impulse magnitude and sine amplitude are 0.5. 1.0 is digital full scale; no clipping is applied in measurement.\n"
         "These deliberately unprimed probes differ from the silence-guarded musical fixtures. Numerical difference is not a quality score.")


def timbre_and_envelope(data, output):
    lookup, names = records_48_stereo(data)
    names = [n for n in names if n != "silence"]
    if not names:
        return
    centroid, envelope, crest, stereo = [], [], [], []
    for name in names:
        baseline = lookup[name, "bypass"]
        baseline_centroid = number(baseline.get("centroid_hz"))
        centroid.append([100 * (number(lookup[name, m].get("centroid_hz")) / baseline_centroid - 1)
                         if baseline_centroid > 0 else np.nan for m in MODES])
        envelope.append([100 * number(lookup[name, m].get("envelope_relative_rms")) for m in MODES])
        crest.append([number(lookup[name, m].get("crest_factor_db")) - number(baseline.get("crest_factor_db")) for m in MODES])
        stereo.append([number(lookup[name, m].get("stereo_correlation_delta")) for m in MODES])
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    heatmap(axes[0, 0], centroid, names, MODE_LABELS,
            "Spectral centroid change", "100 × (centroid / Bypass centroid − 1) (%)", signed=True)
    heatmap(axes[0, 1], envelope, names, MODE_LABELS,
            "1 ms RMS envelope difference, unaltered levels",
            "RMS(envelope − Bypass envelope) / RMS(Bypass envelope) (%)")
    heatmap(axes[1, 0], crest, names, MODE_LABELS,
            "Crest-factor change", "Crest factor − Bypass crest factor (dB)", signed=True)
    heatmap(axes[1, 1], stereo, names, MODE_LABELS,
            "Stereo correlation change", "Pearson correlation − Bypass correlation", signed=True, decimals=4)
    fig.suptitle("Tonal, envelope, and stereo diagnostics · 48 kHz stereo", fontsize=15)
    fig.subplots_adjust(left=0.15, bottom=0.10, right=0.93, top=0.90, wspace=0.65, hspace=0.28)
    save(fig, output, "05_timbre_envelope_stereo",
         FOOTNOTE + "\nEnvelope ratios include level change. Crest factor is level invariant. Whole-source correlation does not fully describe stereo imaging.")


def main():
    global FOOTNOTE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="measurements.json or its containing directory")
    parser.add_argument("--output", type=Path, required=True, help="directory for PNG/SVG figure pairs")
    args = parser.parse_args()
    source = args.input / "measurements.json" if args.input.is_dir() else args.input
    data = json.loads(source.read_text())
    if data.get("kind") != "deterministic-identical-source-live-study":
        raise ValueError("Input is not a controlled LIVE study measurement artifact.")
    args.output.mkdir(parents=True, exist_ok=True)
    is_recordings=not any(r["fixture"] in FIXTURE_ORDER for r in data["measurements"])
    if is_recordings:
        FOOTNOTE=("Verified CC0 Commons recordings; instrumentation/capture technique is not independently established.\n"
                  "Identical resampled, delay-aligned passages. RMS matching is not LUFS matching. Numerical difference is not a quality score.")
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "svg.fonttype": "none",
    })
    generators=(raw_and_matched,pairwise,timbre_and_envelope) if is_recordings else (raw_and_matched,pairwise,frequency_sensitivity,cold_start,timbre_and_envelope)
    for generate in generators:
        generate(data, args.output)
    print(f"Wrote LIVE study PNG/SVG figures to {args.output}")


if __name__ == "__main__":
    main()
