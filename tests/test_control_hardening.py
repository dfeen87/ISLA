"""Retained production transport evidence outside frozen DSP."""
import numpy as np

from isla.control import ControlService
from test_control import make_session


def test_alive_dac_gap_and_underflow_counts_survive_stop(tmp_path):
    c, _, files, *_ = make_session()
    s = ControlService(c)
    c.player.install({"original": np.full((8192, 2), .1, np.float32)}, 48000)
    try:
        s.file_command('play')
        stream = c.player.stream
        stream.pump()
        stream.dac_time += 512 / 48000
        stream.pump(status=type('Flags', (), {'output_underflow': True})())
        state = s.snapshot()
        assert 'underflows=1' in state.alive_health
        assert 'DAC gaps=1' in state.alive_health
        s.file_command('stop')
        assert s.snapshot().alive_health == state.alive_health
        assert stream.closed
    finally:
        s.shutdown()
        c.close()
