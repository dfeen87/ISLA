"""Review reproductions added against PR #88's unmodified implementation."""
import numpy as np

from isla.control import ControlService
from test_control import make_session


def test_changing_speed_after_final_callback_does_not_restart_finished_song():
    controller, _, files, *_ = make_session()
    controller.player.backend.CallbackStop = files.CallbackStop
    service = ControlService(controller)
    controller.player.install({'original':np.full((256,2),.2,np.float32)},48000)
    try:
        service.set_vinyl_slowdown(True)
        service.file_command('play')
        files.streams[-1].pump(512)  # Final source callback, before the 100ms UI poll.
        assert controller.player._ended
        service.set_vinyl_slowdown(False)
        assert controller.player.state == 'completed'
        assert len(files.streams) == 1
    finally:
        service.shutdown()
        controller.close()


def test_odd_final_callback_keeps_the_last_pending_half_frame():
    controller, _, files, *_ = make_session()
    controller.player.backend.CallbackStop = files.CallbackStop
    service = ControlService(controller)
    controller.player.install({'original':np.array([[.2],[.4],[.8]],np.float32)},48000)
    try:
        service.set_vinyl_slowdown(True)
        service.file_command('play')
        native = files.streams[-1]
        first = native.pump(5)
        assert native.active, 'The sixth output frame is still pending; do not stop yet.'
        last = native.pump(1)
        np.testing.assert_allclose(np.concatenate([first,last])[:,0],
                                   np.array([.2,.2,.3,.4,.6,.8])*.25,atol=1e-7)
        assert not native.active
    finally:
        service.shutdown()
        controller.close()


def test_final_callback_racing_pause_does_not_restart_finished_song(monkeypatch):
    controller, _, files, *_ = make_session()
    controller.player.backend.CallbackStop = files.CallbackStop
    service = ControlService(controller)
    controller.player.install({'original':np.full((1024,2),.2,np.float32)},48000)
    try:
        service.file_command('play')
        pause = controller.player.pause
        def finish_then_pause():
            controller.player.cursor = 1024
            controller.player._ended = True
            return pause()
        monkeypatch.setattr(controller.player,'pause',finish_then_pause)
        service.set_vinyl_slowdown(True)
        assert controller.player.state == 'completed'
        assert len(files.streams) == 1
    finally:
        service.shutdown()
        controller.close()
