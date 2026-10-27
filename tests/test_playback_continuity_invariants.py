"""ALIVE playback continuity characterization, outside frozen player/streaming code.

Fake PortAudio callbacks prove PCM/state behavior, NOT physical Mac deadlines,
CoreAudio resampling, DAC continuity, or perceptual audio quality. The three
strict XPASS/XFAIL cases are known safety/continuity gaps awaiting separate
reviewed fixes; they must not be misrepresented as passing invariants.
"""
import numpy as np
import pytest

from isla.playback import BufferPlayer
from test_alive import FakeBackend


@pytest.mark.parametrize("rate", (44100, 48000))
@pytest.mark.parametrize("channels", (1, 2))
def test_nonconstant_song_is_sample_exact_across_unusual_callback_sizes(rate, channels):
    """Count every output sample, including the final zero-padded callback."""
    rng = np.random.default_rng(20261027)
    source = (rng.standard_normal((8197, channels)) * .125).astype(np.float32)
    player = BufferPlayer(FakeBackend())
    player.install({"original": source}, rate)
    player.play()
    stream = player.stream
    pieces = []
    sizes = (512, 64, 1024, 17, 257, 511, 128, 3, 777)
    try:
        for callback_index in range(100):
            if not stream.active:
                break
            pieces.append(stream.pump(sizes[callback_index % len(sizes)]))
        else:
            pytest.fail("Stream did not reach EOF within the callback budget")
        output = np.concatenate(pieces)
        np.testing.assert_array_equal(output[:len(source)], source)
        np.testing.assert_array_equal(output[len(source):], 0)
        np.testing.assert_array_equal(source, player.buffers["original"])
        assert player.cursor == len(source)
        assert len(player.backend.streams) == 1
        player.refresh()
        assert player.state == "completed" and stream.closed
    finally:
        player.close()


@pytest.mark.parametrize("rate", (44100, 48000))
def test_spaced_mode_selections_preserve_pcm_cursor_and_one_stream(rate):
    """Verify nonconstant crossfade PCM at a shared cursor and no stream reopen."""
    rng = np.random.default_rng(683)
    original = (rng.standard_normal((8192, 2)) * .13).astype(np.float32)
    buffers = {
        "original": original,
        "velvet": (original * np.float32(.6)).copy(),
        "legato": (original * np.float32(-.4)).copy(),
        "melt": (original * np.float32(.2)).copy(),
    }
    player = BufferPlayer(FakeBackend())
    player.install(buffers, rate)
    player.play()
    stream = player.stream
    originals = {key: value.copy() for key, value in buffers.items()}
    try:
        np.testing.assert_array_equal(stream.pump(), original[:512])
        old_mode = "original"
        for new_mode in ("velvet", "legato", "melt", "original"):
            start = player.cursor
            player.select(new_mode)
            output = stream.pump()
            n = len(player._fade)
            expected = buffers[new_mode][start:start + 512].copy()
            expected[:n] = (
                buffers[new_mode][start:start + n] * player._fade
                + buffers[old_mode][start:start + n] * player._inverse
            )
            np.testing.assert_allclose(output, expected, rtol=0, atol=1e-7)
            assert player.cursor == start + 512
            assert player.stream is stream
            # Next selection starts only after the 5 ms fade is settled.
            stream.pump()
            old_mode = new_mode
        assert len(player.backend.streams) == 1
        for name in buffers:
            np.testing.assert_array_equal(buffers[name], originals[name])
    finally:
        player.close()


@pytest.mark.xfail(
    strict=True,
    reason="Known gap: a second selection during the 5 ms fade restarts "
           "from the previous *buffer*, not the last audible mixed sample",
)
def test_rapid_mode_retarget_preserves_last_audible_sample():
    """A second button click after 64 frames must not jump toward raw Velvet."""
    original = np.zeros((4096, 2), np.float32)
    velvet = np.ones_like(original)
    legato = -np.ones_like(original)
    player = BufferPlayer(FakeBackend())
    player.install({"original": original, "velvet": velvet, "legato": legato}, 48000)
    player.play()
    try:
        player.stream.pump()
        player.select("velvet")
        first = player.stream.pump(64)
        player.select("legato")
        second = player.stream.pump(64)
        # Both sources are constant; a >0.1 jump here is introduced solely
        # by retargeting the 5 ms crossfade, not by music or the output device.
        assert abs(float(second[0, 0] - first[-1, 0])) <= 0.1
    finally:
        player.close()


@pytest.mark.xfail(
    strict=True,
    reason="Known gap: finished_callback is treated as natural EOF "
           "without confirming that the sample cursor reached the end",
)
def test_premature_native_finished_callback_cannot_report_completed():
    player = BufferPlayer(FakeBackend())
    player.install({"original": np.ones((4096, 2), np.float32)}, 48000)
    player.play()
    stream = player.stream
    try:
        stream.pump()
        assert player.cursor == 512
        stream.active = False
        stream.finished()  # Device/host termination, before EOF.
        player.refresh()
        assert player.state == "paused"
        assert "unexpectedly" in player.warning
    finally:
        player.close()


@pytest.mark.xfail(
    strict=True,
    reason="Known gap: unexpected-inactive stream cleanup drops the DAC "
           "clock before retaining the last audible cursor position",
)
def test_unexpected_output_stop_resumes_at_audible_not_queued_position():
    player = BufferPlayer(FakeBackend())
    player.install({"original": np.ones((4096, 2), np.float32)}, 48000)
    player.play()
    stream = player.stream
    try:
        stream.pump()
        # Only 123 of the 512 queued samples have reached the DAC.
        stream.time = stream.dac_time - (512 - 123) / 48000
        assert player.position == 123
        stream.active = False
        player.refresh()
        assert player.state == "paused"
        assert player.cursor == 123
    finally:
        player.close()
