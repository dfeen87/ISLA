"""Reproduce the new intensity acceptance matrix; never rewrites Experiment 02.

    python -m tools.remastered_verify --output docs/remastered/INTENSITY_MATRIX.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import scipy

from isla.remastered import BASELINE_DEPTHS, RenderRequest, output_metrics, render_preview
from tools.resonance02 import core


def fixture(sr, channels, dtype=np.float32):
    """Synthetic attacks, vibrato, decay, noise and settled silence; no piano claim."""
    t = np.arange(round(sr * 1.2)) / sr
    phase = 2*np.pi*3520*t + .4*np.sin(2*np.pi*4*t)
    envelope = np.where(t < .55, .12, .12*np.exp(-5*(t-.55)))
    mono = envelope * (np.cos(phase) + .3*np.cos(2*np.pi*7053*t))
    mono[t < .06] = 0
    mono[(t >= .72) & (t < .9)] = 0
    rng = np.random.default_rng(20261024)
    mono[(t >= .9) & (t < 1.)] = rng.normal(0, .025, np.count_nonzero((t >= .9) & (t < 1.)))
    mono[t >= 1.08] = 0
    x = mono[:, None] if channels == 1 else np.column_stack((mono, .7*mono))
    return x.astype(dtype)


def verify_matrix():
    cells = []
    for sr in (44100, 48000):
        for channels in (1, 2):
            x = fixture(sr, channels)
            for mode in BASELINE_DEPTHS:
                baseline, _ = core.render(x, sr, mode)
                for intensity in (0, 25, 50, 75, 100):
                    request = RenderRequest(mode, intensity)
                    y, report = render_preview(x, sr, request)
                    replay, _ = render_preview(x, sr, request)
                    report['deterministic_bit_exact'] = y.tobytes() == replay.tobytes()
                    report['zero_bit_exact'] = y.tobytes() == x.tobytes() if intensity == 0 else None
                    report['baseline_bit_exact'] = y.tobytes() == baseline.tobytes() if intensity == 100 else None
                    report['playback_output'] = output_metrics(x, y.astype(np.float32))
                    report['output_sha256'] = hashlib.sha256(y.tobytes()).hexdigest()
                    cells.append(report)
    passed = all(r['numerical_pass'] and r['deterministic_bit_exact'] and
                 r['zero_bit_exact'] is not False and r['baseline_bit_exact'] is not False and
                 r['playback_output']['peak_screen_pass'] for r in cells)
    return dict(schema=1, fixture='synthetic mixed-regime 1.2 s, seed 20261024',
                scope='Post-freeze engineering evidence; not the historical research corpus or listening acceptance',
                python=sys.version, platform=platform.platform(), numpy=np.__version__, scipy=scipy.__version__,
                cells=len(cells), passed=passed, results=cells)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = verify_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(f"{report['cells']} cells: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
