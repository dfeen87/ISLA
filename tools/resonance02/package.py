"""Final evidence QA and checksums; no DSP or measurement thresholds changed."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,zipfile
import numpy as np
import soundfile as sf
from tools.resonance02.run import verify
from tools.resonance02.corpus import array_hash,dump

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

VERIFIER='''"""Standalone SHA256 evidence verifier; run from any working directory."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
manifest=root/'SHA256SUMS.json'
entries=json.loads(manifest.read_text())
failed=[]
for name,expected in entries.items():
    path=root/name
    h=hashlib.sha256()
    if not path.is_file():
        failed.append(name);continue
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    if h.hexdigest()!=expected:failed.append(name)
result=dict(files=len(entries),failed=failed,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
print(json.dumps(result,indent=2))
sys.exit(bool(failed))
'''

def prepare(root):
    root=Path(root).resolve();freeze,mf=verify(root)
    rows=[json.loads(x) for x in (root/'metrics.jsonl').read_text().splitlines()]
    assert len(rows)==1976
    qa=[]
    for row in rows:
        label=row['candidate']
        if label=='bypass' or label.endswith('_noop'):
            assert row['metrics']['relative_waveform_rms']==0
        if 'raw_path' in row:
            p=root/row['raw_path'];x,sr=sf.read(p,always_2d=True,dtype='float32')
            assert sha(p)==row['raw_wav_sha256'] and array_hash(x)==row['output_float32_sha256']
            assert np.isfinite(x).all() and sr==row['cell']['sr'] and x.shape[1]==row['cell']['channels']
            qa.append(dict(path=row['raw_path'],frames=len(x),channels=x.shape[1],sr=sr,finite=True))
    for keyname,subdir in [('BLIND_KEY.json','blind'),('MODE_DISTINCTNESS_KEY.json','mode_distinctness'),
                           ('SLOWDOWN_KEY.json','slowdown_blind')]:
        p=root/'listening'/keyname
        if not p.exists():continue
        data=json.loads(p.read_text());entries=data if isinstance(data,list) else data.get('trials',[])
        for r in entries:
            for side in ('A','B'):
                # Presentation supplements pin their own saved PCM/gain QA separately.
                path=root/'listening'/subdir/r['trial']/(side+'.wav')
                assert path.exists(),path
                x,sr=sf.read(path,always_2d=True)
                assert np.isfinite(x).all()
                if side+'_sha256' in r:assert sha(path)==r[side+'_sha256']
                qa.append(dict(path=str(path.relative_to(root)),frames=len(x),channels=x.shape[1],sr=sr,finite=True))
    for p in (root/'slowdown').glob('*.wav'):
        x,sr=sf.read(p,always_2d=True);assert np.isfinite(x).all()
        qa.append(dict(path=str(p.relative_to(root)),frames=len(x),channels=x.shape[1],sr=sr,finite=True))
    dump(root/'AUDIO_QA.json',dict(status='PASS: saved formats, exact raw float32 hashes, finite audio and frozen inputs',
                                 primary_records=len(rows),checked_audio=qa,
                                 limitations='Does not supply creator listening or clear slowdown failures. Supplement gains have separate QA.'))
    (root/'VERIFY.py').write_text(VERIFIER)

def seal(root):
    root=Path(root).resolve()
    entries={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*'))
             if p.is_file() and p.name not in ('SHA256SUMS.json','SHA256SUMS.txt')}
    dump(root/'SHA256SUMS.json',entries)
    (root/'SHA256SUMS.txt').write_text(''.join(f'{v}  {k}\n' for k,v in entries.items()))
    result=subprocess.run([sys.executable,str(root/'VERIFY.py')],check=True,capture_output=True,text=True)
    print(result.stdout)
    (root.parent/'ISLA-Experiment-02-verification.json').write_text(result.stdout)
    archive=root.parent/'ISLA-Experiment-02.zip'
    assert not archive.exists(),'Never overwrite a sealed archive'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,root.name+'/'+str(p.relative_to(root)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None,'Archive CRC failure'
    (root.parent/'ISLA-Experiment-02-SHA256.txt').write_text(
        f'{sha(archive)}  {archive.name}\n{sha(root/"SHA256SUMS.json")}  ISLA-Experiment-02/SHA256SUMS.json\n')
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(entries),archive_crc='PASS')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','seal'));p.add_argument('--output',required=True,type=Path)
    args=p.parse_args();{'prepare':prepare,'seal':seal}[args.action](args.output)
