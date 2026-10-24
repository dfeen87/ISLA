"""Static research figures from saved measurements; optional matplotlib."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--generated", type=Path, required=True)
    p.add_argument("--recorded", type=Path, required=True)
    p.add_argument("--supplement", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    a, b, s = [json.loads(p.read_text()) for p in (args.generated, args.recorded, args.supplement)]
    rows = a["candidates"] + b["candidates"]
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), layout="constrained")
    for profile, marker in zip(a["sweeps"], ["o", "s", "^"]):
        values = a["sweeps"][profile]
        subsets = [[r for r in rows if r["profile"] == profile and r["amount"] == amount] for amount in values]
        maximum = [max(r["versus_original"]["matched_relative_rms"] or 0 for r in subset)*100 for subset in subsets]
        axes[0].plot(range(3), maximum, marker=marker, label=profile.title())
        for j, amount in enumerate(values):
            axes[0].annotate(str(amount), (j, maximum[j]), xytext=(3, 6), textcoords="offset points", fontsize=8)
    axes[0].set(xticks=range(3), xticklabels=["Low", "Center", "High"], ylabel="Largest matched residual / original RMS (%)", title="Waveform distinction across all 56 source/format cells")
    axes[0].legend(frameon=False)
    labels, lo, hi = [], [], []
    for profile, amount in a["showcase"].items():
        values = [r["versus_original"]["rms_gain_db"] for r in rows if r["profile"] == profile and r["amount"] == amount and r["versus_original"]["rms_gain_db"] is not None]
        labels.append(f"{profile.title()} {amount}")
        lo.append(min(values)); hi.append(max(values))
    axes[1].hlines(range(3), lo, hi, color="#31577b", linewidth=4)
    axes[1].plot(lo, range(3), "|", color="#31577b"); axes[1].plot(hi, range(3), "|", color="#31577b")
    axes[1].axvline(0, color=".5", linewidth=.8)
    axes[1].set(yticks=range(3), yticklabels=labels, xlabel="Raw RMS movement versus original (dB)", title="Center settings: level change is measured separately")
    fig.savefig(args.output / "sweep-overview.png", dpi=170)
    fig.savefig(args.output / "sweep-overview.svg")
    plt.close(fig)
    diagnostics = s["attack_diagnostics"]
    fig, axes = plt.subplots(len(diagnostics), 1, figsize=(9.5, 7.5), layout="constrained")
    for ax, r in zip(np.atleast_1d(axes), diagnostics):
        t = (np.array(r["time_seconds"]) - r["reference_peak_seconds"]) * 1000
        baseline, candidate = np.array(r["original_envelope_slope"]), np.array(r["candidate_envelope_slope"])
        scale = np.max(abs(baseline))
        ax.plot(t, baseline / scale, label="Original", linewidth=1.3)
        ax.plot(t, candidate / scale, label="Experiment", linewidth=1.1, linestyle="--")
        ax.axvline(0, color=".4", linewidth=.8)
        ax.axvline(r["picked_shift_ms"], color=".4", linewidth=.8, linestyle=":")
        ax.set(xlabel="Time relative to original picked slope peak (ms)", ylabel="Normalized slope", title=f"{r['profile'].title()} {r['amount']} · 44.1 kHz / {r['channels']} ch · picked shift {r['picked_shift_ms']:.2f} ms · local waveform lag 0 samples")
        ax.legend(frameon=False, loc="lower right")
    fig.savefig(args.output / "attack-screen-diagnostics.png", dpi=170)
    fig.savefig(args.output / "attack-screen-diagnostics.svg")
    plt.close(fig)
    for svg in args.output.glob("*.svg"):
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")


if __name__ == "__main__":
    main()
