"""Compare corrected LIVE against the preserved study; never open audio devices.

Reuses original input hashes, measurements, recordings and cached baseline audio.
Only corrected renders are recomputed. Unprimed edge probes use the frozen
baseline implementation so the whole emitted startup interval remains visible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import soundfile as sf
from isla.streaming import StreamingDSP, MODES
from dsp_study_baseline import StreamingDSP as BaselineDSP
from dsp_study import metrics, recording_sources, relative
from dsp_study_fixtures import fixtures


def render(x,rate,mode,factory=StreamingDSP):
    dsp=factory(rate,x.shape[1]);dsp.select(mode)
    count=((len(x)+dsp.delay+511)//512)*512
    padded=np.pad(x,((0,count-len(x)),(0,0)))
    raw=np.concatenate([dsp.process_block(b) for b in padded.reshape(-1,512,x.shape[1])])
    return raw[dsp.delay:dsp.delay+len(x)],raw


def reference(x,strength):
    """Independent complete-prehistory overlap sum with the stated correction."""
    n,ch=x.shape;w=np.hanning(2049)[:-1,None]
    total=np.zeros((n+4096,ch));weights=np.zeros((n+4096,1))
    # Explicit virtual silence contributes weights even when its spectrum is 0.
    for start in range(-3072,((n+511)//512)*512,512):
        frame=np.zeros((2048,ch))
        lo,hi=max(0,start),min(n,start+2048)
        if hi>lo:frame[lo-start:hi-start]=x[lo:hi]
        wx=frame*w;z=np.fft.rfft(wx,axis=0);m=np.abs(z)
        p=np.pad(m,((1,1),(0,0)))
        sm=(1-strength/2)*m+strength/4*(p[:-2]+p[2:])
        # Conservative float32 ingress uncertainty, not a musical/noise threshold.
        tiny=float(np.nextafter(np.float32(0),np.float32(1)))/2
        floor=np.finfo(np.float32).eps*np.sum(abs(wx),axis=0)+tiny*2048
        gain=np.divide(z,np.maximum(m,floor),out=np.zeros_like(z),where=np.maximum(m,floor)>0)
        changed=z+(sm-m)*gain
        reconstructed=np.fft.irfft(changed,n=2048,axis=0)*w
        src_lo=max(0,-start-1536);src_hi=min(2048,n+4096-start-1536)
        if src_hi>src_lo:
            dest=start+1536+src_lo
            total[dest:dest+src_hi-src_lo]+=reconstructed[src_lo:src_hi]
            weights[dest:dest+src_hi-src_lo]+=w[src_lo:src_hi]**2
    return (total/np.maximum(weights,1e-8))[1536:1536+n]


def main():
    p=argparse.ArgumentParser();p.add_argument("--study-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    baseline={};hashes={}
    for sub in ("", "music"):
        data=json.loads((a.study_root/sub/"measurements.json").read_text())
        baseline.update({(r['rate'],r['channels'],r['fixture'],r['mode']):r for r in data['measurements']})
        hashes.update({(r['rate'],r['channels'],r['fixture']):r['sha256'] for r in data['fixtures']})
    rows=[];invariants=[];source_meta=[];audio_files=[]
    for rate in (44100,48000):
        for ch in (1,2):
            sources=fixtures(rate,ch)
            recordings,meta=recording_sources([a.study_root/"recordings/Emotional_piano.wav",
                a.study_root/"recordings/Katanga.wav"],rate,ch)
            source_meta.extend(meta);sources.update(recordings)
            for name,x in sources.items():
                assert hashlib.sha256(x.tobytes()).hexdigest()==hashes[rate,ch,name]
                banks={mode:render(x,rate,mode) for mode in MODES}
                assert np.array_equal(banks['bypass'][0],x)
                for mode,(y,raw) in banks.items():
                    measured=dict(rate=rate,channels=ch,fixture=name,mode=mode,**metrics(y,x,rate,raw))
                    if mode!='bypass':
                        independent=reference(x,dict(velvet=.35,legato=.55,melt=.75)[mode])
                        measured['independent_wola_max_error']=float(np.max(abs(y-independent)))
                        np.testing.assert_allclose(y,independent,atol=1e-7,rtol=1e-6)
                    row=dict(current=measured,baseline=baseline[rate,ch,name,mode])
                    if rate==48000 and ch==2 and (name in recordings or name in
                        ('solo_piano','connected_melody','percussion','dense_mix')):
                        sub='music' if name in recordings else 'synthetic'
                        dest=a.output/sub/'audio/raw';dest.mkdir(parents=True,exist_ok=True)
                        audio_path=dest/f'{name}_{mode}.wav'
                        sf.write(audio_path,y,rate,subtype='FLOAT')
                        audio_files.append(dict(path=str(audio_path.relative_to(a.output)),
                            sha256=hashlib.sha256(audio_path.read_bytes()).hexdigest(),
                            rate=rate,channels=ch,frames=len(y),fixture=name,mode=mode))
                        cached=a.study_root/('music' if name in recordings else '')/'audio/raw'/f'{name}_{mode}.wav'
                        old,sr=sf.read(cached,dtype='float32',always_2d=True)
                        assert sr==rate and old.shape==y.shape
                        row['cached_baseline_waveform_relative_difference']=relative(y,old)
                        row['cached_baseline_waveform_max_difference']=float(np.max(abs(y-old)))
                    rows.append(row)
                wet=[banks[m][0].astype(float) for m in MODES[1:]]
                invariants.append(dict(rate=rate,channels=ch,fixture=name,
                    midpoint_max_error=float(np.max(abs(wet[1]-(wet[0]+wet[2])/2)))))
                print(f'validated {rate}Hz {ch}ch {name}',flush=True)
    cold=[]
    for rate in (44100,48000):
        for ch in (1,2):
            for source in ('dc_0.5','cos20_0.5','impulse_0.5'):
                x=np.full((8192,ch),.5,np.float32)
                if source=='cos20_0.5':x[:]=(.5*np.cos(2*np.pi*20*np.arange(len(x))/rate))[:,None]
                if source=='impulse_0.5':x[1:]=0
                for mode in MODES:
                    record=dict(rate=rate,channels=ch,source=source,mode=mode)
                    for label,factory in [('baseline',BaselineDSP),('current',StreamingDSP)]:
                        aligned,raw=render(x,rate,mode,factory)
                        record[label]=dict(raw_peak=float(np.max(abs(raw))),
                            pre_delay_peak=float(np.max(abs(raw[:1536]))),samples_over_fullscale=int(np.sum(abs(raw)>1)))
                    cold.append(record)
    root=Path(__file__).resolve().parents[1]
    source_hashes={str(q.relative_to(root)):hashlib.sha256(q.read_bytes()).hexdigest()
                  for q in [root/'isla/streaming.py',root/'isla/spectral.py',root/'tools/dsp_study_baseline.py']}
    result=dict(kind='LIVE numerical robustness before-after',baseline_commit='4eb2412682f8b3c6321ce5c8887314850ac9a697',
        processing='virtual silent WOLA prehistory + float32-uncertainty-bounded spectral correction',
        artistic_strengths=[.35,.55,.75],musical_tuning_changed=False,perceptual_acceptance=False,
        python=platform.python_version(),numpy=np.__version__,soundfile=sf.__version__,platform=platform.platform(),
        source_sha256=source_hashes,input_hashes_verified=True,measurements=rows,invariants=invariants,
        cold_start=cold,recording_transformations=source_meta,audio_files=audio_files)
    (a.output/'before_after.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(f'validated {len(rows)} current mode measurements; reused recorded baseline metrics/audio',flush=True)


if __name__=='__main__':main()
