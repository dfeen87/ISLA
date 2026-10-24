"""Post-freeze LIVE equivalence, control evidence and bounded-state benchmark."""
import argparse
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

from isla.live_engine import LiveEngineDSP,LiveSettings
from isla.remastered import CORE_SHA256,RenderRequest,output_metrics
from isla.remastered_streaming import RemasteredStreamingDSP
from tools.remastered_verify import fixture
from tools.resonance02 import core


def matrix():
    rows = []
    for sr in (44100,48000):
        for channels in (1,2):
            x = fixture(sr,channels)
            padded = np.pad(x,((0,(-len(x))%512+1536),(0,0)))
            for mode in core.MODES:
                for intensity in (0,25,50,75,100):
                    dsp = RemasteredStreamingDSP(sr,channels,intensity); dsp.select(mode)
                    output,controls = [],[]
                    max_phase,max_gain,min_gain = 0.,1.,1.
                    for block in padded.reshape(-1,512,channels):
                        output.append(dsp.process_block(block)); controls.append(dsp.control[core.MODES.index(mode)])
                        if mode == 'melt': max_phase = max(max_phase,dsp.last_phase_max)
                        bounds = dsp.last_gain_ranges[core.MODES.index(mode)]
                        min_gain,max_gain = min(min_gain,float(bounds[0])),max(max_gain,float(bounds[1]))
                    y = np.concatenate(output)[1536:1536+len(x)]
                    ref,diagnostic = core.render(x,sr,mode,cfg=RenderRequest(mode,intensity).configuration())
                    reference = ref.astype(np.float32)
                    error = float(np.max(np.abs(y-reference)))
                    row = dict(mode=mode,intensity=intensity,sample_rate=sr,channels=channels,
                        requested_depth=RenderRequest(mode,intensity).depth,
                        actual_depth_mean=float(np.mean(controls)),actual_depth_max=float(np.max(controls)),
                        vetoed_frames=dsp.vetoed,frames=dsp.frames,
                        control_reference_max_error=float(np.max(np.abs(np.array(controls)-diagnostic['control']))),
                        phase_max_rad=max_phase,spectral_gain_min=min_gain,spectral_gain_max=max_gain,
                        max_sample_error_to_frozen_float32=error,float32_bit_exact=y.tobytes()==reference.tobytes(),
                        zero_source_bit_exact=y.tobytes()==x.tobytes() if intensity == 0 else None,
                        output=output_metrics(x,y))
                    row['passed'] = bool(error <= 1e-7 and row['control_reference_max_error'] <= 1e-14
                        and min_gain >= .8 and max_gain <= 1.188502227 and max_phase <= .1
                        and row['zero_source_bit_exact'] is not False and np.isfinite(y).all())
                    rows.append(row)
    return rows


def benchmark():
    rows = []
    for sr in (44100,48000):
        settings = LiveSettings();settings.set('remastered',100)
        engine = LiveEngineDSP(sr,2,settings);engine.select('melt')
        t = np.arange(512)/sr
        block = np.column_stack((.1*np.sin(2*np.pi*3520*t),.07*np.sin(2*np.pi*3520*t+.3))).astype(np.float32)
        times,retained = [],[]
        for n in range(1056):
            started = time.perf_counter();engine.process_block(block)
            elapsed = (time.perf_counter()-started)*1000
            if n >= 32: times.append(elapsed)
            if n in (31,1055): retained.append(sum(a.nbytes for a in vars(engine.research).values() if isinstance(a,np.ndarray)))
        rows.append(dict(sample_rate=sr,channels=2,measured_hops=len(times),budget_ms=512/sr*1000,
            mean_ms=float(np.mean(times)),p99_ms=float(np.percentile(times,99)),max_ms=max(times),
            hops_over_budget=int(np.count_nonzero(np.array(times)>512/sr*1000)),
            retained_research_array_bytes_before=retained[0],retained_research_array_bytes_after=retained[1],
            bounded_retained_state=retained[0]==retained[1]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    cells,bench = matrix(),benchmark()
    report = dict(schema=1,authority_core_sha256=CORE_SHA256,python=sys.version,numpy=np.__version__,
        platform=platform.platform(),scope='Post-freeze engineering evidence; not native audio/listening acceptance',
        latency_samples=1536,sample_equivalence_tolerance=1e-7,control_equivalence_tolerance=1e-14,
        passed=all(r['passed'] for r in cells) and all(r['bounded_retained_state'] for r in bench),
        cells=len(cells),results=cells,worker_benchmark=bench)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(f"{report['cells']} cells: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
