"""Filename discovery is read-only, cancellable and ambiguity-aware."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from isla.file_search import choose_match,find_audio,is_bare_filename,rank_matches
from isla.preparation import Preparation
from isla.search_preparation import SearchPreparation
from isla.terminal import TerminalController
from test_alive import FakeBackend, wait_ready


def test_mac_spotlight_is_computer_wide_and_acc_alias_finds_aac(monkeypatch,tmp_path):
    path = tmp_path/'Dancing Queen.aac'; path.touch()
    calls = []
    def run(args,**kwargs):
        calls.append((args,kwargs))
        return SimpleNamespace(stdout=str(path).encode()+b'\0')
    monkeypatch.setattr('isla.file_search.sys.platform','darwin')
    matches,info = find_audio('Dancing Queen.ACC',roots=[],runner=run)
    assert matches == [path]
    assert calls[0][0] == ['/usr/bin/mdfind','-0','-name','Dancing Queen']
    assert '-onlyin' not in calls[0][0] and calls[0][1]['timeout'] == 8
    assert choose_match('Dancing Queen.ACC',matches,info) == path


def test_track_number_m4a_fallback_case_and_exact_name_priority(tmp_path):
    music = tmp_path/'Music'/'ABBA'; music.mkdir(parents=True)
    m4a = music/'03 Dancing Queen.m4a'; m4a.touch()
    matches,info = find_audio('Dancing Queen.ACC',roots=[music])
    assert matches == [m4a]
    assert choose_match('Dancing Queen.ACC',matches,info) == m4a
    exact = music/'Dancing Queen.AAC'; exact.touch()
    assert rank_matches('Dancing Queen.acc',[m4a,exact,exact]) == [exact]
    assert rank_matches('Dancing Queen.AAC',[m4a,exact]) == [exact]


def test_multiple_matches_are_listed_for_explicit_selection(tmp_path):
    paths = [tmp_path/'one'/'Dancing Queen.aac',tmp_path/'two'/'Dancing Queen.aac']
    for path in paths: path.parent.mkdir(); path.touch()
    with pytest.raises(ValueError,match='Multiple') as exc:
        choose_match('Dancing Queen.ACC',paths,dict(indexed=True,truncated=False))
    assert all(str(path) in str(exc.value) for path in paths)
    assert 'full path' in str(exc.value)
    with pytest.raises(ValueError,match='incomplete'):
        choose_match('Dancing Queen.ACC',paths[:1],dict(indexed=True,truncated=True))


def test_index_failure_falls_back_and_limits_are_reported(monkeypatch,tmp_path):
    path = tmp_path/'song.wav'; path.touch()
    def fail(*a,**k): raise subprocess.TimeoutExpired('mdfind',8)
    monkeypatch.setattr('isla.file_search.sys.platform','darwin')
    matches,info = find_audio('song.wav',roots=[tmp_path],runner=fail,max_entries=1)
    assert matches == [path] and info == dict(indexed=False,truncated=True)
    with pytest.raises(ValueError,match='full path'):
        choose_match('missing.wav',[],dict(indexed=False,truncated=False))


@pytest.mark.parametrize('value',['/Music/song.wav','~/Music/song.wav','Music/song.wav',''])
def test_explicit_paths_do_not_trigger_computer_search(value):
    assert not is_bare_filename(value)


def test_actual_search_process_loads_file_from_music_subdirectory_and_cancels(tmp_path,monkeypatch):
    music = tmp_path/'Music'/'Artist'; music.mkdir(parents=True)
    path = music/'unique-search-test.wav'
    x = np.zeros((1024,2),np.float32)
    sf.write(path,x,44100,subtype='FLOAT')
    monkeypatch.chdir(tmp_path)
    job = SearchPreparation(path.name,Preparation)
    try:
        buffers,sr = wait_ready(job)
        assert sr == 44100 and job.path == path
        np.testing.assert_array_equal(buffers['original'],x)
        assert 'Found' in job.state
        directory = Path(job.directory.name)
    finally: job.close(); job.close()
    assert not directory.exists()
    pending = SearchPreparation('missing-cancel-test.wav',Preparation)
    process = pending.process
    pending.close()
    assert process._closed


def test_terminal_missing_basename_searches_but_full_path_keeps_original_error(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    song = tmp_path/'Music'/'song.wav'; song.parent.mkdir()
    sf.write(song,np.zeros((1024,1)),48000)
    c = TerminalController(FakeBackend())
    try:
        with pytest.raises(ValueError,match='not found'):
            c.execute('load "'+str(tmp_path/'wrong'/'song.wav')+'"')
        c.execute('load song.wav')
        assert isinstance(c.job,SearchPreparation) and 'Searching' in c.job.state
        buffers,sr = wait_ready(c.job)
        assert c.job.path == song and sr == 48000
        assert buffers['original'].shape == (1024,1)
    finally: c.close()
