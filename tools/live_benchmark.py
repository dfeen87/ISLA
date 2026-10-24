"""Reproducible synthetic DSP timing, not native capture/output acceptance.

Run from the installed checkout: python tools/live_benchmark.py
No audio device is opened and no audio samples are saved.
"""
import json
import platform
import time

import numpy as np

from isla.streaming import MODES, StreamingDSP


def main():
    results = []
    for rate in (44100, 48000):
        for channels in (1, 2):
            dsp = StreamingDSP(rate, channels)
            rng = np.random.default_rng(2026)
            block = rng.normal(0, .1, (512, channels)).astype(np.float32)
            elapsed = []
            for i in range(600):
                dsp.select(MODES[(i // 50) % 4])
                start = time.perf_counter()
                dsp.process_block(block)
                if i >= 20:
                    elapsed.append((time.perf_counter() - start) * 1000)
            results.append(dict(rate=rate, channels=channels, blocks=600,
                hop_budget_ms=512 / rate * 1000, algorithmic_delay_ms=dsp.delay / rate * 1000,
                dsp_p50_ms=float(np.percentile(elapsed, 50)), dsp_p99_ms=float(np.percentile(elapsed, 99)),
                dsp_max_ms=max(elapsed), retained_array_bytes=sum(
                    value.nbytes for value in vars(dsp).values() if isinstance(value, np.ndarray))))
    print(json.dumps(dict(kind="synthetic-worker-only", platform=platform.platform(),
                         python=platform.python_version(), numpy=np.__version__, results=results), indent=2))


if __name__ == "__main__":
    main()
