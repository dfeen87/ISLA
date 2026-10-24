"""Worker-body budget experiments, no devices or native realtime guarantee.

Measures finite scans, RMS meters, all warm DSP banks and two bounded rings as
in LiveMonitor._work. Excludes .25s routing inspection, backend/device behavior,
and GIL callback scheduling. One paced stereo run samples wakeup lateness under
two explicit CPU competitors; these are synthetic load, not browser emulation.
"""
from __future__ import annotations
import argparse
import json
import multiprocessing as mp
import os
import platform
import resource
import time
from pathlib import Path

import numpy as np
from isla.live import BlockRing
from isla.streaming import MODES, StreamingDSP
from dsp_study_fixtures import fixtures


def competitor(stop,ready):
    rng=np.random.default_rng(99)
    x=rng.normal(size=(4096,4))
    for _ in range(20):
        x=np.fft.irfft(np.fft.rfft(x,axis=0),n=4096,axis=0)
    ready.set()
    while not stop.is_set():
        # Separate processes compete for CPU/memory without touching audio state.
        for _ in range(20):
            x=np.fft.irfft(np.fft.rfft(x,axis=0),n=4096,axis=0)
        sum(i*i for i in range(3000))


def distribution(x):
    a=np.asarray(x)
    return dict(count=len(a),p50_ms=float(np.percentile(a,50)),
        p95_ms=float(np.percentile(a,95)),p99_ms=float(np.percentile(a,99)),
        p999_ms=float(np.percentile(a,99.9)),max_ms=float(np.max(a)))


def measure(rate,ch,blocks,paced=False):
    dsp=StreamingDSP(rate,ch)
    source=fixtures(rate,ch)["dense_mix"]
    source=source[:len(source)//512*512].reshape(-1,512,ch)
    incoming,outgoing=BlockRing(ch),BlockRing(ch)
    block=np.empty((512,ch),np.float32); sink=np.empty_like(block)
    times=[]; late=[]; misses=0; completion_late=[]
    deadline=time.perf_counter()
    for i in range(blocks+32):
        if paced:
            remaining=deadline-time.perf_counter()
            if remaining>0: time.sleep(remaining)
            late.append(max(0,time.perf_counter()-deadline)*1000)
        assert incoming.push(source[i%len(source)],i*512/rate)
        started=time.perf_counter()
        stamp=incoming.pop_into(block)
        assert stamp is not None
        if not np.isfinite(block).all(): block.fill(0)
        input_rms=float(np.sqrt(np.mean(np.square(block,dtype=np.float64))))
        dsp.select(MODES[(i//50)%4])
        result=dsp.process_block(block)
        assert result.shape==block.shape and np.isfinite(result).all()
        output_rms=float(np.sqrt(np.mean(np.square(result,dtype=np.float64))))
        assert outgoing.push(result,stamp-dsp.delay/rate)
        elapsed=(time.perf_counter()-started)*1000
        if i>=32:
            times.append(elapsed)
            misses+=elapsed>512/rate*1000
            if paced: completion_late.append(max(0,late[-1]+elapsed-512/rate*1000))
        assert outgoing.pop_into(sink) is not None
        if paced: deadline+=512/rate
    return dict(rate=rate,channels=ch,pace="hop-clock" if paced else "throughput",
        budget_ms=512/rate*1000,worker_body=distribution(times),budget_exceedances=misses,
        wakeup_lateness=distribution(late[32:]) if paced else None,
        paced_completion_deadline_misses=sum(x>0 for x in completion_late) if paced else None,
        paced_completion_lateness_max_ms=max(completion_late,default=0) if paced else None,
        retained_array_bytes=sum(v.nbytes for v in vars(dsp).values() if isinstance(v,np.ndarray)),
        ring_bytes=incoming.data.nbytes+outgoing.data.nbytes+incoming.stamps.nbytes+outgoing.stamps.nbytes,
        input_high_water=incoming.high_water,output_high_water=outgoing.high_water,
        final_input_rms=input_rms,final_output_rms=output_rms)


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    p.add_argument("--blocks",type=int,default=3000)
    p.add_argument("--paced-blocks",type=int,default=1200)
    args=p.parse_args();results=[]
    for load in (False,True):
        stop=mp.get_context("spawn").Event()
        workers=[]
        try:
            if load:
                ready=[mp.get_context("spawn").Event() for _ in range(2)]
                workers=[mp.get_context("spawn").Process(target=competitor,args=(stop,event)) for event in ready]
                for w in workers:w.start()
                assert all(event.wait(30) for event in ready),"competitors failed to initialize"
            for rate in (44100,48000):
                for ch in (1,2):
                    result=measure(rate,ch,args.blocks)
                    result["load"]="2 CPU competitor processes" if load else "ambient host"
                    results.append(result);print(json.dumps(result),flush=True)
            if load:
                result=measure(48000,2,args.paced_blocks,True)
                result["load"]="2 CPU competitor processes"
                results.append(result);print(json.dumps(result),flush=True)
        finally:
            stop.set()
            for w in workers:w.join(5)
            for w in workers:
                if w.is_alive():w.terminate();w.join()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(kind="synthetic-worker-body-budget",results=results,
        platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,cpu_count=os.cpu_count(),
        process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if platform.system()=="Darwin" else 1024),
        rss_note="macOS process peak incl. fixture generation; not DSP retained state or bounded scratch proof",
        excludes=["native callback/GIL scheduling",".25s route inspection","devices","physical latency"],
        queue_note="rings drained each hop; high-water bounds here do not establish live queue scheduling"),indent=2)+"\n")


if __name__=="__main__":main()
