"""Execute only an immutable, hash-verified Experiment 02 freeze."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import numpy as np
import psutil
import soundfile as sf
from scipy.signal import resample_poly
from tools.resonance02 import core
from tools.resonance02.corpus import file_hash, array_hash, dump
from tools.resonance02.legacy01 import render as legacy_render
from tools.resonance02.measure import metrics, reference, rms, peak, envelope, tone_frequency
from tools.resonance02.slowdown import stretch

REPO=Path(__file__).resolve().parents[2]
DOCS=REPO/'docs/research/phase-governed-resonance-02'

def source_files():
    folders=(REPO/'tools/resonance02',REPO/'isla',REPO/'phased_music_notes',DOCS)
    return sorted([p for folder in folders for p in folder.rglob('*')
                   if p.is_file() and p.suffix in ('.py','.md','.lock')]+
                  [REPO/'tools/dsp_study_fixtures.py'])

def freeze(root):
    root=Path(root)
    assert not (root/'FREEZE.json').exists(),'Freeze is write-once'
    paths={str(p.relative_to(REPO)):file_hash(p) for p in source_files()}
    data=dict(schema=1,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              baseline='20a32de76396ab3400f14c5169276d6f03b72d08',config=asdict(core.Config()),
              source_manifest_sha256=file_hash(root/'SOURCE_MANIFEST.json'),code_and_protocol=paths,
              python=sys.version,platform=platform.platform(),
              dependencies={d:metadata.version(d) for d in ('numpy','scipy','soundfile','librosa','matplotlib','pytest','psutil')})
    dump(root/'FREEZE.json',data)
    print('Frozen',file_hash(root/'FREEZE.json'),flush=True)

def verify(root):
    f=json.loads((root/'FREEZE.json').read_text())
    assert file_hash(root/'SOURCE_MANIFEST.json')==f['source_manifest_sha256']
    for p,sha in f['code_and_protocol'].items():assert file_hash(REPO/p)==sha, f'Frozen file changed: {p}'
    assert asdict(core.Config())==f['config']
    subprocess.run(['git','diff','--exit-code',f['baseline'],'--','isla','phased_music_notes',
                    'drivers','src','pyproject.toml','CMakeLists.txt'],cwd=REPO,check=True,capture_output=True)
    mf=json.loads((root/'SOURCE_MANIFEST.json').read_text())
    for c in mf['cells']:assert file_hash(root/c['path'])==c['sha256']
    return f,mf

def conventional(x,sr):
    e=envelope(x,sr);mem=0.;history=np.empty(len(e))
    attack=np.exp(-1/(sr*.005));release=np.exp(-1/(sr*.08))
    for i,value in enumerate(e):
        rho=attack if value>mem else release
        mem=rho*mem+(1-rho)*value;history[i]=mem
    gain=np.clip(history/np.maximum(e,1e-10),.8,1.188502227)
    gain[e<1e-5]=1.
    return x*gain[:,None]

def governance_summary(a,d,sr):
    u=d['control'];g=a['states'];f=a['features'];active=f[:,8]==0
    return dict(processing_percent=float(np.mean(u>1e-8)*100),
                attack_protection_percent=float(np.mean(f[:,6]>=.5)*100),
                attack_processed_frames=int(np.sum((f[:,6]>=.5)&(u>0))),
                regime_transitions=int(np.sum(np.diff(np.argmax(g,axis=1))!=0)),
                regime_transitions_per_s=float(np.sum(np.diff(np.argmax(g,axis=1))!=0)/(len(u)*512/sr)),
                state_mean=g.mean(axis=0).tolist(),confidence_percentiles=np.percentile(f[:,5],[0,25,50,75,100]).tolist(),
                ambiguity_mean=float(np.mean(1-np.max(g,axis=1))),
                entropy_mean=float(np.mean(-np.sum(g*np.log(np.maximum(g,1e-12)),axis=1))),
                effective_depth=d['effective_depth'],rate_limit_frames=d['rate_limit_frames'],
                gain_limit_frames=d['gain_limit_frames'],fallback_frames=d['fallback_frames'],
                phase_max_rad=d['phase_max'],gain_min=d['gain_min'],gain_max=d['gain_max'],
                analysis_array_bytes=sum(v.nbytes for v in a.values() if isinstance(v,np.ndarray)))

def listening_pairs(root,cell,versions,rng,key,trial_index):
    name=cell['name'];sr=cell['sr']
    pairs=[]
    for mode in core.MODES:
        pairs.extend([('bypass',mode+'_governed'),(mode+'_fixed_matched',mode+'_governed'),
                      (mode+'_exp01',mode+'_governed')])
    pairs.append(('bypass','bypass'))
    for label1,label2 in pairs:
        first,second=versions[label1],versions[label2]
        match=rms(first)/rms(second) if rms(second)>1e-12 else 1.
        a,b=first,second*match
        pk=max(peak(resample_poly(a,4,1,axis=0)),peak(resample_poly(b,4,1,axis=0)))
        common=min(1.,.8/pk) if pk else 1.
        arrays=[a*common,b*common];labels=[label1,label2]
        gains=[common,common*match]
        if rng.integers(2):arrays.reverse();labels.reverse();gains.reverse()
        tid=f'T{trial_index:03d}';folder=root/'listening'/'blind'/tid;folder.mkdir(parents=True,exist_ok=True)
        for side,array in zip(('A','B'),arrays):sf.write(folder/(side+'.wav'),array,sr,subtype='FLOAT')
        key.append(dict(trial=tid,source=name,A=labels[0],B=labels[1],gain_A=gains[0],gain_B=gains[1],
                        matching='scalar RMS plus common 4x peak headroom, not perceptual loudness',
                        rate=sr,channels=cell['channels'],frames=len(first),
                        A_sha256=file_hash(folder/'A.wav'),B_sha256=file_hash(folder/'B.wav')))
        trial_index+=1
    return trial_index

def evaluate(root):
    f,mf=verify(root)
    assert not (root/'metrics.jsonl').exists(),'Do not overwrite an evaluation'
    (root/'raw').mkdir();(root/'states').mkdir();(root/'metrics.jsonl').touch()
    start=time.perf_counter();records=[];blind=[];trial=1;rng=np.random.default_rng(20261024)
    for ci,cell in enumerate(mf['cells']):
        x,sr=sf.read(root/cell['path'],always_2d=True,dtype='float64')
        a=core.analyze(x,sr);ref=reference(x,sr,cell);versions={'bypass':x.copy()};ds={}
        render_times={'bypass':0.}
        # Production and Exp01 retain their exact float32 ingress and original mode selection fades.
        for mode,amount in [('velvet',.20),('legato',.50),('melt',.30)]:
            for label,amounts in [(mode+'_production',None),(mode+'_exp01',{mode:amount})]:
                t=time.perf_counter();versions[label],raw=legacy_render(x.astype(np.float32),sr,mode,amounts)
                render_times[label]=time.perf_counter()-t
            for variant in core.VARIANTS:
                label=mode+'_'+variant;t=time.perf_counter()
                versions[label],ds[label]=core.render(x,sr,mode,variant,analysis=a)
                render_times[label]=time.perf_counter()-t
        t=time.perf_counter();versions['envelope_control']=conventional(x,sr)
        render_times['envelope_control']=time.perf_counter()-t
        selected=sr==48000 and cell['channels']==2 and cell['name'] in (
            'recorded_piano','recorded_piano_reserved','connected_melody','harmonic_sustain')
        controls={}
        for label,y in versions.items():
            m=metrics(x,y,sr,cell,ref)
            r=dict(cell={k:cell[k] for k in ('name','sr','channels','kind','partition')},candidate=label,
                   output_float32_sha256=array_hash(y),render_seconds=render_times[label],
                   render_realtime_factor=render_times[label]/(len(x)/sr),metrics=m)
            if label in ds:
                r['governance']=governance_summary(a,ds[label],sr);controls[label]=ds[label]['control']
            if selected:
                folder=root/'raw'/cell['name'];folder.mkdir(exist_ok=True)
                sf.write(folder/(label+'.wav'),y,sr,subtype='FLOAT')
                r['raw_path']=str((folder/(label+'.wav')).relative_to(root))
                r['raw_wav_sha256']=file_hash(folder/(label+'.wav'))
            records.append(r)
            with (root/'metrics.jsonl').open('a') as stream:stream.write(json.dumps(r,allow_nan=False)+'\n')
        if selected:
            np.savez_compressed(root/'states'/(cell['name']+'.npz'),time=a['time'],features=a['features'],
                                states=a['states'],resonance=a['resonance'],**controls)
            trial=listening_pairs(root,cell,versions,rng,blind,trial)
        print(f'{ci+1}/{len(mf["cells"])} {cell["name"]} {sr}/{cell["channels"]}: {len(versions)} records',flush=True)
        del versions,a,ref
    dump(root/'listening'/'BLIND_KEY.json',blind)
    summary={}
    for label in sorted({r['candidate'] for r in records}):
        group=[r for r in records if r['candidate']==label]
        summary[label]=dict(cells=len(group),failed_cells=sum(bool(r['metrics']['screen_failures']) for r in group),
                            failure_counts=dict(Counter(e for r in group for e in r['metrics']['screen_failures'])),
                            unresolved_attack_cells=sum(bool(r['metrics']['unresolved_flags']) for r in group),
                            max_sample_peak=max(r['metrics']['sample_peak'] for r in group),
                            max_4x_peak=max(r['metrics']['oversampled_4x_peak'] for r in group),
                            mean_effective_depth=float(np.mean([r['governance']['effective_depth'] for r in group if 'governance'in r])) if any('governance'in r for r in group) else None)
    dump(root/'SUMMARY.json',dict(candidates=summary,records=len(records),cells=len(mf['cells']),
                               freeze_sha256=file_hash(root/'FREEZE.json'),elapsed_seconds=time.perf_counter()-start,
                               process_peak_rss_bytes=psutil.Process().memory_info().peak_wset if hasattr(psutil.Process().memory_info(),'peak_wset') else __import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss,
                               rss_units='bytes on macOS; high water mark for this process',listening_trials=len(blind)))

def slowdown_evaluation(root):
    _,mf=verify(root);dest=root/'slowdown';dest.mkdir(exist_ok=False);rows=[]
    for name in ('recorded_piano','recorded_piano_reserved','harmonic_sustain','impulse','simple_tone'):
        cell=next(c for c in mf['cells'] if c['name']==name and c['sr']==48000 and c['channels']==2)
        x,sr=sf.read(root/cell['path'],always_2d=True)
        for ratio in (1.25,1.5):
            for protected in (False,True):
                y,d=stretch(x,sr,ratio,protected=protected)
                prefix=f'{name}_r{ratio:.2f}_{"protected" if protected else "raw"}'
                sf.write(dest/(prefix+'.wav'),y,sr,subtype='FLOAT')
                d.update(source=name,path=prefix+'.wav',sha256=file_hash(dest/(prefix+'.wav')))
                if name=='simple_tone':
                    fy=tone_frequency(y,sr,440);fx=tone_frequency(x,sr,440)
                    d['pitch_delta_cents']=float(1200*np.log2(fy/fx))
                rows.append(d)
                if protected and name in ('recorded_piano','recorded_piano_reserved','harmonic_sustain'):
                    for mode in core.MODES:
                        z,controls=core.render(y,sr,mode)
                        label=prefix+'_'+mode
                        sf.write(dest/(label+'.wav'),z,sr,subtype='FLOAT')
                        rows.append(dict(source=name,ratio=ratio,identity=mode,path=label+'.wav',
                                         sha256=file_hash(dest/(label+'.wav')),output_samples=len(z),
                                         sample_peak=peak(z),oversampled_4x_peak=peak(resample_poly(z,4,1,axis=0)),
                                         effective_depth=controls['effective_depth'],creator_listening='PENDING'))
            # Established unprotected reference, independently applied channels. Its stereo caveat is explicit.
            import librosa
            channels=[]
            for c in range(x.shape[1]):
                X=librosa.stft(x[:,c],n_fft=2048,hop_length=512)
                V=librosa.phase_vocoder(X,rate=1/ratio,hop_length=512,n_fft=2048)
                channels.append(librosa.istft(V,hop_length=512,length=round(len(x)*ratio)))
            z=np.array(channels).T;label=f'{name}_r{ratio:.2f}_librosa_reference'
            sf.write(dest/(label+'.wav'),z,sr,subtype='FLOAT')
            rows.append(dict(source=name,ratio=ratio,reference='librosa.phase_vocoder, independent channels, no transient treatment',
                             path=label+'.wav',sha256=file_hash(dest/(label+'.wav')),output_samples=len(z),
                             sample_peak=peak(z),oversampled_4x_peak=peak(resample_poly(z,4,1,axis=0))))
        print('Slowdown',name,flush=True)
    dump(dest/'metrics.json',dict(records=rows,gate='INCOMPLETE: frozen impulse timing failures; creator listening pending'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('freeze','evaluate','slowdown'))
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    {'freeze':freeze,'evaluate':evaluate,'slowdown':slowdown_evaluation}[args.action](args.output.resolve())
