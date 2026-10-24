"""Prepare checksum-pinned inputs before measurements, never overwrite Exp01."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from tools.dsp_study_fixtures import fixtures, fixture_manifest

PIANO_HASH='9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15'

def file_hash(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array_hash(x): return hashlib.sha256(np.asarray(x,dtype='<f4').tobytes()).hexdigest()
def dump(p,data): Path(p).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def prepare(root, piano, old_evidence):
    root=Path(root); root.mkdir(parents=True,exist_ok=False)
    (root/'sources').mkdir();(root/'provenance').mkdir()
    assert file_hash(piano)==PIANO_HASH, 'Unverified recorded source'
    shutil.copyfile(piano,root/'sources'/'Emotional_piano_original.wav')
    for name in ('generated-measurements.json','recorded-measurements.json'):
        shutil.copyfile(Path(old_evidence)/name,root/'provenance'/('exp01-'+name))
    old=json.loads((Path(old_evidence)/'generated-measurements.json').read_text())['source_records']
    old+=json.loads((Path(old_evidence)/'recorded-measurements.json').read_text()).get('sources',[])
    # Recorded source manifest lives in provenance; baseline hash is identical to dry source.
    recorded=json.loads((Path(old_evidence)/'recorded-measurements.json').read_text())
    old += [dict(fixture=r['fixture'],rate=r['rate'],channels=r['channels'],
                 float32_le_sha256=r['float32_le_sha256']) for r in recorded['baselines'] if r['mode']=='bypass']
    previous={(r['fixture'],r['rate'],r['channels']):r['float32_le_sha256'] for r in old}
    original,native=sf.read(piano,always_2d=True,dtype='float64')
    assert native==44100 and original.shape==(705600,2)
    cells=[]
    def save(name,x,sr,events=(),**extra):
        x=np.asarray(x,dtype=np.float32);ch=x.shape[1]
        p=root/'sources'/f'{name}_{sr}_{ch}.wav';sf.write(p,x,sr,subtype='FLOAT')
        ah=array_hash(x);known=previous.get((name,sr,ch))
        cells.append(dict(name=name,sr=sr,channels=ch,frames=len(x),path=str(p.relative_to(root)),
                          sha256=file_hash(p),float32_le_sha256=ah,events_seconds=list(events),
                          exp01_hash=known,exp01_match=(ah==known) if known else None,**extra))
    for sr in (44100,48000):
        for ch in (1,2):
            generated=fixtures(sr,ch);mf=fixture_manifest(sr,ch)['fixtures']
            generated['near_silence']=generated['simple_tone']*np.float32(1e-7)
            x=generated['simple_tone'].copy()
            start,stop,edge=round(2.1*sr),round(2.4*sr),round(.01*sr)
            fade=(.5+.5*np.cos(np.pi*np.arange(edge)/(edge-1)))[:,None]
            x[start-edge:start]*=fade;x[start:stop]=0;x[stop:stop+edge]*=fade[::-1]
            generated['gapped_tone']=x
            for name,x in generated.items():
                events=[e['time_seconds'] for e in mf.get(name,{}).get('events',[])]
                save(name,x,sr,events,kind='synthetic',partition='reused-known')
            for name,start_s in [('recorded_piano',2),('recorded_piano_reserved',9)]:
                x=original[start_s*native:(start_s+6)*native]
                if sr!=native:x=resample_poly(x,160,147,axis=0)
                if ch==1:x=x.mean(axis=1,keepdims=True)
                x=np.pad(x,((round(.125*sr),round(.125*sr)),(0,0)))
                save(name,x,sr,kind='recorded',partition='reused-known' if start_s==2 else 'reserved-same-recording',
                     original_seconds=[start_s,start_s+6],license='CC0-1.0')
    # Long records resolve slow beating; stereo variants include fixed L/R phase separation.
    sr=48000; t=np.arange(20*sr)/sr
    for base in (440.,3520.):
        for delta in (.2,1.,1.5,3.):
            for damped in (False,True):
                x=.12*(np.cos(2*np.pi*base*t)+np.cos(2*np.pi*(base+delta)*t))
                if damped:x*=np.exp(-t/6.)
                x=np.pad(x[:,None],((6000,6000),(0,0)))
                save(f'beat_{int(base)}_{delta:g}_{"damped" if damped else "steady"}',x,sr,[.125],
                     kind='beating',base_hz=base,delta_hz=delta,tau_s=6. if damped else None,
                     partition='new-ground-truth')
    matches=[c for c in cells if c['exp01_match'] is not None]
    assert len(matches)==56 and all(c['exp01_match'] for c in matches), 'Exp01 inputs changed'
    manifest=dict(schema=1,seed=20261024,recorded_original_sha256=PIANO_HASH,
                  license_source='https://freesound.org/people/triangelx/sounds/189175/',
                  cells=cells,verified_exp01_cells=len(matches),
                  generation_source_sha256=file_hash(__file__))
    dump(root/'SOURCE_MANIFEST.json',manifest)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--piano',type=Path,required=True);p.add_argument('--old-evidence',type=Path,required=True)
    a=p.parse_args();m=prepare(a.output,a.piano,a.old_evidence)
    print(f'Prepared {len(m["cells"])} cells; all {m["verified_exp01_cells"]} Experiment 01 cells match')
