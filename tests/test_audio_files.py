"""Local Apple purchase import, using generated audio rather than user music."""
import multiprocessing as mp
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pytest
import soundfile as sf

from isla import audio_files
from isla.preparation import MODES, Preparation
from isla.local_preparation import NativePreparation, _prepare_native, prepare_file
from drivers.api import IslaBuffer
from test_alive import wait_ready

MAC_ONLY = pytest.mark.skipif(sys.platform != 'darwin', reason='Native macOS codecs')


@pytest.mark.parametrize('suffix', ['.m4p', '.M4P', '.movpkg'])
def test_protected_downloads_have_actionable_error(tmp_path, suffix):
    path = tmp_path / ('Purchased song' + suffix)
    if suffix == '.movpkg':
        path.mkdir()
    else:
        path.write_bytes(b'protected')
    with pytest.raises(ValueError, match='DRM-free purchased AAC'):
        prepare_file(path)


def test_aac_header_is_deferred_only_on_mac(tmp_path, monkeypatch):
    path = tmp_path / 'Song.M4A'
    path.write_bytes(b'not a libsndfile format')
    monkeypatch.setattr(audio_files.sys, 'platform', 'linux')
    with pytest.raises(ValueError, match='requires macOS'):
        audio_files.inspect_audio(path)
    monkeypatch.setattr(audio_files.sys, 'platform', 'darwin')
    assert audio_files.inspect_audio(path) is None
    # Do not run the external decoder during the caller's header check.
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('decoded on caller'))
    assert audio_files.inspect_audio(path) is None


@pytest.mark.parametrize('extension,format', [('.flac', 'FLAC'), ('.aiff', 'AIFF')])
def test_existing_lossless_decoders_preserve_audio(tmp_path, extension, format):
    path = tmp_path / ('song' + extension)
    sf.write(path, np.zeros((512, 2)), 48000, format=format)
    assert audio_files.inspect_audio(path).samplerate == 48000
    job = prepare_file(path)
    try:
        assert type(job) is Preparation
        buffers, rate = wait_ready(job)
        assert buffers['original'].shape == (512, 2) and rate == 48000
    finally:
        job.close()


@MAC_ONLY
@pytest.mark.parametrize('codec,format,extension', [
    ('aac', 'm4af', '.m4a'), ('alac', 'm4af', '.M4A'), ('aac', 'adts', '.aac')])
@pytest.mark.parametrize('sr,channels', [(44100, 1), (48000, 2)])
def test_real_apple_audio_prepares_all_modes(tmp_path, codec, format, extension, sr, channels):
    source = tmp_path / 'source.wav'
    t = np.arange(sr // 4) / sr
    mono = .2 * np.sin(2 * np.pi * 440 * t)
    sf.write(source, np.column_stack([mono * (1 - .2 * ch) for ch in range(channels)]), sr)
    original, _ = sf.read(source, dtype='float32', always_2d=True)
    path = tmp_path / ('Purchased song café with spaces' + extension)
    subprocess.run(['/usr/bin/afconvert', '-f', format, '-d', codec,
                    str(source), str(path)], check=True, capture_output=True)
    before = path.read_bytes()
    job = prepare_file(path)
    directory = Path(job.directory.name)
    try:
        buffers, loaded_sr = wait_ready(job)
        assert loaded_sr == sr
        decoded = buffers['original']
        assert decoded.dtype == np.float32 and decoded.shape[1] == channels
        assert np.isfinite(decoded).all()
        if codec == 'alac':
            np.testing.assert_array_equal(decoded, original)
        elif extension == '.m4a':
            # M4A carries the packet table needed to trim AAC priming/padding.
            assert decoded.shape == original.shape
            assert np.sqrt(np.mean((decoded - original) ** 2)) < .01
        else:
            assert len(decoded) >= len(original) and np.max(np.abs(decoded)) > .1
        for mode in MODES:
            expected = IslaBuffer(mode=mode, sr=sr).process_buffer(decoded)
            np.testing.assert_array_equal(buffers[mode], expected.astype('float32'))
        assert not (directory / 'decoded.wav').exists()
        assert path.read_bytes() == before
    finally:
        job.close()
    assert not directory.exists()


@MAC_ONLY
def test_invalid_m4a_worker_error_and_cleanup(tmp_path):
    path = tmp_path / 'broken.m4a'
    path.write_bytes(b'not audio')
    job = prepare_file(path)
    directory = Path(job.directory.name)
    try:
        with pytest.raises(ValueError, match='DRM-free purchased AAC'):
            wait_ready(job)
        assert not (directory / 'decoded.wav').exists()
    finally:
        job.close()
    assert not directory.exists()


def _slow_native_decode(path, directory, connection, pid_file):
    """Exercise the real worker/decode path with a controllably slow converter."""
    run = subprocess.run

    def slow_run(*args, **kwargs):
        return run([sys.executable, '-c',
                    'import os, pathlib, sys, time; '
                    'pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)',
                    str(pid_file)], **kwargs)

    audio_files.subprocess.run = slow_run
    _prepare_native(path, directory, connection)


@MAC_ONLY
def test_close_cancels_native_decoder_and_removes_temporary_files(tmp_path):
    path = tmp_path / 'pending.m4a'
    path.write_bytes(b'native decode needed')
    pid_file = tmp_path / 'decoder.pid'
    # Own the same process/pipe/tempdir as a normal Preparation, replacing only
    # the afconvert invocation with a slow child so cancellation is deterministic.
    import tempfile
    job = NativePreparation.__new__(NativePreparation)
    job.directory = tempfile.TemporaryDirectory(prefix='isla-alive-test-')
    context = mp.get_context('spawn')
    job.connection, child = context.Pipe(duplex=False)
    job.process = context.Process(target=_slow_native_decode,
                                  args=(str(path), job.directory.name, child, pid_file))
    job.process.start()
    child.close()
    directory = Path(job.directory.name)
    try:
        deadline = time.monotonic() + 15
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert pid_file.exists(), 'Decoder did not start'
        pid = int(pid_file.read_text())
    finally:
        job.close()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)],
                                capture_output=True, text=True).stdout.strip()
        if not status or status.startswith('Z'):
            break
        time.sleep(.01)
    else:
        pytest.fail('Native decoder is still running after cancellation')
    assert not directory.exists()
