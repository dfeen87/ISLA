"""GUI-only rapid-mode serialization; never alter frozen BufferPlayer/DSP.

The PortAudio stand-in deliberately uses sub-512 callbacks to expose two mode
clicks inside one 5 ms fade. The controller must publish the newest request
only after the old audible fade is complete. These are PCM-level tests, NOT
native Mac timing or listening claims.
"""
import numpy as np
import pytest

from isla.control import ControlService
from test_control import make_session


@pytest.mark.parametrize("rate", [44100, 48000])
def test_second_gui_mode_click_does_not_retarget_unfinished_crossfade(rate):
    c, _, files, *_ = make_session()
    service = ControlService(c)
    original = np.zeros((4096, 2), np.float32)
    velvet = np.ones_like(original)
    legato = -np.ones_like(original)
    c.player.install({"original": original, "velvet": velvet, "legato": legato}, rate)
    try:
        service.file_command("play")
        stream = files.streams[0]
        stream.pump()
        service.file_command("mode velvet")
        first = stream.pump(64)
        assert c.player._fade_pos == 64
        reply = service.file_command("mode legato")
        assert "waiting" in reply
        assert c.player.mode == "velvet"
        assert "queued: Legato" in service.snapshot().alive_applied_mode
        service.poll()  # This check must NOT apply the second mode mid-fade.
        assert c.player.mode == "velvet"

        remaining = len(c.player._fade) - 64
        complete = stream.pump(remaining)
        assert c.player._fade_pos == len(c.player._fade)
        service.poll()  # Now Legato can be safely selected.
        assert c.player.mode == "legato"
        after = stream.pump(64)
        # The synthetic sources are constant: a >0.1 discontinuity would
        # come from resetting the second fade against the raw Velvet buffer.
        expected_gain = service._alive_gui_backend.output_level_percent / 100
        assert abs(float(after[0, 0] - complete[-1, 0])) <= .1 * expected_gain
        assert float(first[-1, 0]) < float(complete[-1, 0])
        assert len(files.streams) == 1
        assert c.player.stream is stream
    finally:
        service.shutdown()
        c.close()


def test_rapid_gui_mode_requests_coalesce_latest_and_cancel_on_stop():
    c, _, files, *_ = make_session()
    service = ControlService(c)
    c.player.install({
        "original": np.zeros((4096, 2), np.float32),
        "velvet": np.ones((4096, 2), np.float32),
        "legato": -np.ones((4096, 2), np.float32),
        "melt": np.full((4096, 2), .25, np.float32),
    }, 48000)
    try:
        service.file_command("play")
        stream = files.streams[0]
        stream.pump()
        service.file_command("mode velvet")
        stream.pump(64)
        service.file_command("mode legato")
        service.file_command("mode melt")
        assert c.player.mode == "velvet"
        assert "queued: Melt" in service.snapshot().alive_applied_mode
        stream.pump(len(c.player._fade) - 64)
        service.poll()
        assert c.player.mode == "melt"
        assert service._deferred_file_mode is None
        assert len(files.streams) == 1

        stream.pump(64)
        service.file_command("mode legato")
        assert service._deferred_file_mode == "mode legato"
        service.file_command("stop")
        assert service._deferred_file_mode is None
        assert c.player.cursor == 0 and c.player.state == "stopped"
        service.poll()
        assert c.player.mode == "melt"  # Stale request must not revive.
        service.file_command("mode legato")  # Stopped selection remains immediate.
        assert c.player.mode == "legato"
    finally:
        service.shutdown()
        c.close()


def test_rapid_gui_pending_selection_dropped_on_pause_or_new_source():
    c, _, files, *_ = make_session()
    service = ControlService(c)
    c.player.install({
        "original": np.zeros((4096, 2), np.float32),
        "velvet": np.ones((4096, 2), np.float32),
        "legato": -np.ones((4096, 2), np.float32),
    }, 48000)
    try:
        service.file_command("play")
        stream = files.streams[0]
        stream.pump()
        service.file_command("mode velvet")
        stream.pump(64)
        service.file_command("mode legato")
        assert service._deferred_file_mode == "mode legato"
        service.file_command("pause")
        service.poll()
        assert service._deferred_file_mode is None
        assert c.player.mode == "velvet"
        service.load_file("replacement.wav")
        assert service._deferred_file_mode is None
        assert c.player.state == "idle"
        assert not c.player.buffers
    finally:
        service.shutdown()
        c.close()
