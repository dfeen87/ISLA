"""Lossless, no-overwrite ALIVE Save Mix acceptance; no sound device required."""
import time

import numpy as np
import pytest
import soundfile as sf

from isla.control import ControlService
from isla.mix_export import MixExport
from test_control import make_session


def done(export, timeout=7):
    deadline = time.monotonic() + timeout
    while export.pending:
        if time.monotonic() > deadline:
            pytest.fail('Mix export did not finish')
        time.sleep(.005)


@pytest.mark.parametrize('mode,value', [('original', .2), ('velvet', .4),
                                        ('legato', .6), ('melt', .8)])
def test_save_selected_prepared_mode_unattenuated_original_preserved(tmp_path, mode, value):
    c, live, files, *_ = make_session()
    service = ControlService(c)
    audio = {m: np.full((8192, 2), v, np.float32)
             for m, v in (('original', .2), ('velvet', .4),
                          ('legato', .6), ('melt', .8))}
    c.player.install(audio, 48000)
    try:
        if mode != 'original':
            service.file_command('mode ' + mode)
        target = tmp_path / f'{mode}-ISLA.wav'
        service.save_mix(str(target))
        done(service.mix_export)
        assert target.exists(), service.mix_export.status
        output, rate = sf.read(str(target), dtype='float32', always_2d=True)
        assert rate == 48000
        np.testing.assert_array_equal(output, audio[mode])
        np.testing.assert_array_equal(audio['original'], .2 * np.ones((8192, 2), np.float32))
        assert service.snapshot().saved_path == str(target)
        assert service.snapshot().save_mode == mode
        assert not live.streams
        # No GUI playback attenuation is baked into a scientific/source buffer.
        np.testing.assert_allclose(output, value, atol=1e-6)
        with pytest.raises(FileExistsError):
            service.save_mix(str(target))
        np.testing.assert_array_equal(sf.read(str(target), dtype='float32',
                                              always_2d=True)[0], output)
    finally:
        service.shutdown()
        c.close()


def test_export_cancel_prevents_partial_destination_and_cleans_temp(tmp_path):
    export = MixExport()
    export.CHUNK_FRAMES = 128  # Makes cancellation deterministic without large fixtures.
    audio = np.full((200000, 2), .2, np.float32)
    path = tmp_path / 'cancel.wav'
    export.start(audio, 44100, 'velvet', str(path))
    export.cancel()
    done(export)
    assert not path.exists()
    assert not list(tmp_path.glob('.isla-mix-*'))
    assert 'canceled' in export.status


def test_nonfinite_and_invalid_or_overwrite_targets_fail_closed(tmp_path):
    export = MixExport()
    audio = np.full((2048, 1), np.nan, dtype=np.float32)
    target = tmp_path / 'reject.wav'
    export.start(audio, 48000, 'melt', str(target))
    done(export)
    assert not target.exists()
    assert 'nonfinite' in export.status
    assert not list(tmp_path.glob('.isla-mix-*'))
    with pytest.raises(ValueError, match='only .wav'):
        export.start(audio, 48000, 'melt', str(tmp_path / 'bad.flac'))
    existing = tmp_path / 'original.wav'
    existing.write_bytes(b'protected original')
    with pytest.raises(FileExistsError):
        export.start(np.zeros((512, 1), np.float32), 48000, 'melt', str(existing))
    assert existing.read_bytes() == b'protected original'


def test_save_completed_governed_remastered_buffer_exactly(tmp_path):
    """Remastered saving uses only the validated, applied DSP result."""
    from test_remastered_preparation import ready_service
    service, controller, _ = ready_service(tmp_path)
    try:
        service.enter_remastered()
        service.prepare_remastered('velvet', 50)
        service.preview.job.complete()
        service.poll()
        assert controller.player.mode == 'remastered_velvet'
        expected = controller.player.buffers['remastered_velvet'].copy()
        output = tmp_path / 'governed-velvet.wav'
        service.save_mix(str(output))
        done(service.mix_export)
        assert output.is_file(), service.mix_export.status
        actual, sr = sf.read(str(output), always_2d=True, dtype='float32')
        assert sr == 48000
        np.testing.assert_array_equal(actual, expected)
        assert controller.player.buffers['original'].shape == expected.shape
        assert service.snapshot().research_active
    finally:
        service.shutdown()
        controller.close()
