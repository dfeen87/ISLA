"""Fetch the two reviewed CC0 originals, verifying bytes before incorporation.

Licensing/authorship evidence is in the study's RECORDING_PROVENANCE.md/JSON.
No playback, capture, transcoding, or routing. Existing matching bytes reused.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES=(
    ("Emotional_piano.wav","https://upload.wikimedia.org/wikipedia/commons/7/70/Emotional_piano.wav",
     "9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15"),
    ("Katanga.wav","https://upload.wikimedia.org/wikipedia/commons/b/bf/Katanga.wav",
     "5782e604fcac61a25bacf449f0ce9ce74555d13fb68ab62050f5cdcdcda89fc3"),
)


def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    for name,url,expected in SOURCES:
        path=args.output/name
        if path.exists():
            data=path.read_bytes()
        else:
            request=Request(url,headers={"User-Agent":"ISLA-DSP-Study/1.0 (controlled CC0 audio research)"})
            with urlopen(request,timeout=60) as response:data=response.read()
        actual=hashlib.sha256(data).hexdigest()
        if actual!=expected:
            raise ValueError(f"{name}: checksum mismatch {actual}; do not incorporate changed source bytes")
        if not path.exists():path.write_bytes(data)
        print(f"verified {name}: {actual}")


if __name__=="__main__":main()
