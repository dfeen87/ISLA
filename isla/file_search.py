"""Read-only local audio discovery: Spotlight across this Mac, bounded fallback."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import time

AUDIO_SUFFIXES = {'.wav','.aif','.aiff','.flac','.mp3','.m4a','.aac','.mp4','.ogg','.opus','.caf','.alac'}


def is_bare_filename(value):
    return bool(value) and '/' not in value and '\\' not in value and not value.startswith('~')


def _title(path):
    # Music libraries commonly prepend a track/disc number to the title.
    return re.sub(r'^\d+(?:[-.]\d+)?[\s.-]+','',Path(path).stem).casefold().strip()


def rank_matches(query, paths):
    requested = Path(query)
    corrected = requested.with_suffix('.aac') if requested.suffix.casefold() == '.acc' else requested
    ranked = []
    seen = set()
    for item in paths:
        path = Path(item).expanduser()
        if not path.is_file() or path.suffix.casefold() not in AUDIO_SUFFIXES:
            continue
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        rank = (0 if path.name.casefold() == requested.name.casefold() else
                1 if path.name.casefold() == corrected.name.casefold() else
                2 if _title(path) == requested.stem.casefold().strip() else 3)
        if rank < 3:
            ranked.append((rank,path))
    if not ranked:
        return []
    best = min(rank for rank,_ in ranked)
    return sorted((path for rank,path in ranked if rank == best),key=lambda p:str(p).casefold())


def find_audio(query, *, roots=None, runner=subprocess.run, max_entries=50000, seconds=10):
    candidates = []
    indexed = sys.platform == 'darwin'
    if indexed:
        try:
            result = runner(['/usr/bin/mdfind','-0','-name',Path(query).stem],
                capture_output=True,check=True,timeout=8)
            candidates.extend(os.fsdecode(item) for item in result.stdout.split(b'\0') if item)
        except (OSError,subprocess.SubprocessError):
            indexed = False
    # Indexes can omit a newly downloaded Music file. Also inspect accessible
    # user media folders; no symlink traversal, index changes or permission hacks.
    roots = roots if roots is not None else [Path.cwd(),*(Path.home()/name for name in
        ('Music','Downloads','Desktop','Documents'))]
    started, count, truncated = time.monotonic(),0,False
    for root in roots:
        if not Path(root).is_dir():
            continue
        for directory, dirs, files in os.walk(root,followlinks=False):
            dirs[:] = [name for name in dirs if not name.startswith('.') and
                       name not in ('node_modules','Library')]
            count += len(dirs)+len(files)
            for name in files:
                if Path(name).suffix.casefold() in AUDIO_SUFFIXES and (
                        name.casefold() == Path(query).name.casefold() or _title(name) == Path(query).stem.casefold().strip()):
                    candidates.append(Path(directory)/name)
            if count >= max_entries or time.monotonic()-started >= seconds:
                truncated = True
                break
        if truncated:
            break
    return rank_matches(query,candidates),dict(indexed=indexed,truncated=truncated)


def choose_match(query, matches, info):
    if len(matches) == 1 and not info['truncated']:
        return matches[0]
    if matches:
        listing = '\n'.join(f'  [{i}] {path}' for i,path in enumerate(matches[:10],1))
        detail = (' Search reached its folder limit; more matches may exist.' if info['truncated'] else '')
        raise ValueError(f'Multiple or incomplete matches for {query!r}.{detail}\n{listing}\n'
                         'Choose a file with load "<full path>" or Open Audio File in the window.')
    raise ValueError(f'No matching local audio found for {query!r}. Searched '+
        ('this Mac’s Spotlight index and accessible media folders.' if info['indexed'] else 'accessible media folders.')+
        (' Search reached its folder limit.' if info['truncated'] else '')+
        ' Unindexed, unavailable or inaccessible files require their full path or the file picker.')
