"""Paired synthetic worker timing with the existing unmodified benchmark body."""
import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dsp_study_benchmark as worker
from isla.streaming import StreamingDSP
from tools.identity_lab.dsp import IdentityDSP, SHOWCASE, SWEEPS


def arrays(obj, prefix=""):
    found = {}
    for name, value in vars(obj).items():
        key = prefix + name
        if isinstance(value, np.ndarray):
            found[key] = (value.shape, value.nbytes)
        elif name == "blenders":
            for i, adapter in enumerate(value):
                found.update(arrays(adapter, f"{key}.{i}."))
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    records = []
    for rate in (44100, 48000):
        for channels in (1, 2):
            for label in ("baseline", *SHOWCASE, "all_maximum"):
                amounts = ({k: max(v) for k, v in SWEEPS.items()} if label == "all_maximum"
                           else {label: SHOWCASE[label]} if label in SHOWCASE else {})
                dsp = (IdentityDSP(rate, channels, amounts) if amounts else StreamingDSP(rate, channels))
                initial = arrays(dsp)
                worker.StreamingDSP = lambda _rate, _channels: dsp
                record = worker.measure(rate, channels, 1500)
                assert arrays(dsp) == initial
                record.update(profile=label, amounts=amounts, load="ambient host; sequential paired cells",
                    nested_retained_array_bytes=sum(value[1] for value in initial.values()),
                    unchanged_array_shapes=True)
                records.append(record)
                print(f"Measured worker {rate}/{channels}/{label}", flush=True)
    # A longer cyclic input including near-silence and zero confirms finite,
    # settled state under warmed rapid selection at the largest amounts.
    dsp = IdentityDSP(48000, 2, {k: max(v) for k, v in SWEEPS.items()})
    before = arrays(dsp)
    rng = np.random.default_rng(750)
    block = rng.normal(0, .1, (512, 2)).astype(np.float32)
    for i in range(20000):
        dsp.select(("bypass", *SWEEPS)[i % 4])
        output = dsp.process_block(block * (0 if i % 100 > 90 else 1e-7 if i % 100 > 80 else 1))
        assert np.isfinite(output).all()
    assert arrays(dsp) == before
    args.output.write_text(json.dumps(dict(kind="synthetic worker only", platform=platform.platform(),
        records=records, long_state_run_hops=20000, long_state_shapes_unchanged=True,
        exclusions=["native callback/GIL scheduling", "device routing checks", "physical devices", "hardware latency", "explicit competing CPU load"],
        note="Rings, finite scans and RMS meters included using original benchmark body; no deadline guarantee or speedup claim."), indent=2)+"\n")


if __name__ == "__main__":
    main()
