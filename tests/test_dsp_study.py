"""Scientific invariants of research measurements; no audio devices or recordings."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from isla.streaming import MODES, StreamingDSP
from tools import dsp_study_fixtures as sources


@pytest.fixture(scope="module")
def study():
    # The standalone research command imports its sibling fixture module.
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
        yield importlib.import_module("dsp_study")


@pytest.mark.parametrize("rate,channels", [(8000, 1), (96000, 2), (44100, 0), (48000, 3)])
def test_fixture_rejects_unsupported_configuration(rate, channels):
    with pytest.raises(ValueError, match="44100/48000"):
        sources.fixtures(rate, channels)


@pytest.mark.parametrize("rate,channels", [(44100, 1), (44100, 2), (48000, 1), (48000, 2)])
def test_fixture_duration_and_guards_cover_supported_rates(rate, channels):
    frames, guard = sources._configuration(rate, channels)
    assert frames == 6 * rate
    assert guard >= 4096
    assert guard / rate == pytest.approx(.125, abs=1 / rate)


def test_original_fixtures_repeat_exactly_and_have_auditable_provenance():
    # Build only one representative fixture configuration twice, not the full
    # musical rendering matrix. The experiment itself covers all four formats.
    first = sources.fixtures(48000, 2)
    repeated = sources.fixtures(48000, 2)
    manifest = sources.fixture_manifest(48000, 2)
    json.dumps(manifest, allow_nan=False)
    assert tuple(first) == tuple(repeated) == sources.FIXTURE_NAMES
    assert manifest["schema_version"] == 1
    assert manifest["samplerate"] == 48000 and manifest["channels"] == 2
    assert manifest["provenance"]["external_audio"] is False
    assert manifest["provenance"]["recording"] is False
    assert manifest["provenance"]["seed"] == sources.SEED
    guard = manifest["silence_guard_frames"]
    for name, audio in first.items():
        np.testing.assert_array_equal(audio, repeated[name])
        assert not np.shares_memory(audio, repeated[name])
        assert audio.dtype == np.float32 and audio.shape == (288000, 2)
        assert np.isfinite(audio).all()
        assert not np.any(audio[:guard]) and not np.any(audio[-guard:])
        assert np.max(np.abs(audio)) <= manifest["source_peak_limit"]
        metadata = manifest["fixtures"][name]
        assert metadata["source_peak"] == float(np.max(np.abs(audio)))
        assert metadata["frames"] == len(audio) and metadata["channels"] == 2
        for event in metadata["events"]:
            assert guard / 48000 <= event["time_seconds"]
            assert event["time_seconds"] + event["duration_seconds"] <= 6 - guard / 48000 + 1 / 48000


@pytest.mark.parametrize("rate,channels", [(44100, 1), (44100, 2), (48000, 1), (48000, 2)])
def test_mode_renders_receive_identical_samples_fresh_state_and_delay(study, monkeypatch, rate, channels):
    created = []

    class ObservedDSP(StreamingDSP):
        def __init__(self, samplerate, count):
            super().__init__(samplerate, count)
            assert not np.any(self.history) and not np.any(self.tails)
            prehistory = np.zeros_like(self.weights)
            for shift in (512, 1024, 1536):
                prehistory[:-shift] += self.window[shift:] ** 2
            np.testing.assert_array_equal(self.weights, prehistory)
            assert not np.any(self.dry)
            self.received = []
            created.append(self)

        def process_block(self, block):
            self.received.append(block.copy())
            return super().process_block(block)

    monkeypatch.setattr(study, "StreamingDSP", ObservedDSP)
    audio = np.random.default_rng(85).normal(0, .1, (4097, channels)).astype(np.float32)
    original = audio.copy()
    banks = {mode: study.render(audio, rate, mode) for mode in MODES}
    assert len(created) == 4
    for mode, processor in zip(MODES, created):
        supplied = np.concatenate(processor.received)
        np.testing.assert_array_equal(supplied[:len(audio)], original)
        assert not np.any(supplied[len(audio):])
        np.testing.assert_array_equal(supplied, np.concatenate(created[0].received))
        aligned, raw = banks[mode]
        assert aligned.shape == audio.shape
        np.testing.assert_array_equal(aligned, raw[1536:1536 + len(audio)])
    dry, raw = banks["bypass"]
    assert not np.any(raw[:1536])
    np.testing.assert_array_equal(dry, original)
    np.testing.assert_array_equal(audio, original)
    # A later render must recreate its state; prior calls must not leak history.
    np.testing.assert_array_equal(study.render(audio, rate, "melt")[0], banks["melt"][0])


@pytest.mark.parametrize("rate,channels", [(44100, 1), (48000, 2)])
@pytest.mark.parametrize("mode,strength", [("velvet", .35), ("legato", .55), ("melt", .75)])
def test_research_alignment_matches_independent_wola_for_partial_last_hop(study, rate, channels, mode, strength):
    # Finite arbitrary data covers edges and a non-hop-multiple ending. This
    # tests the study's padding/coordinates independently of transport framing.
    audio = np.random.default_rng(91).uniform(-.2, .2, (4097, channels)).astype(np.float32)
    aligned, _ = study.render(audio, rate, mode)
    reference = study.batch_reference(audio, strength)
    np.testing.assert_allclose(aligned, reference, atol=1e-7, rtol=1e-6)
    np.testing.assert_allclose(study.batch_reference(audio, 0), audio, atol=1e-12, rtol=0)


def test_silence_ratios_are_undefined_and_json_serializable(study):
    zero = np.zeros((4096, 2), np.float32)
    assert study.relative(zero, zero) is None
    assert study.relative(np.ones_like(zero), zero) is None
    measured = study.metrics(zero, zero, 48000, zero)
    for key in ("relative_rms", "rms_gain_db", "matched_relative_rms", "optimal_gain_residual",
                "crest_factor_db", "stereo_correlation", "stereo_correlation_delta",
                "envelope_relative_rms", "matched_envelope_relative_rms",
                "waveform_correlation_lag_samples", "centroid_hz"):
        assert measured[key] is None
    assert measured["band_energy_fraction"] == [None] * 4
    assert measured["onset_offsets_ms"] == []
    assert measured["peak"] == measured["raw_peak"] == measured["rms"] == 0
    assert measured["samples_over_fullscale"] == measured["raw_samples_over_fullscale"] == 0
    json.dumps(measured, allow_nan=False)


@pytest.mark.parametrize("constant_channel", [0, 1])
def test_constant_stereo_channel_has_undefined_correlation(study, constant_channel):
    audio = np.random.default_rng(101).normal(0, .1, (4096, 2))
    audio[:, constant_channel] = .25
    assert study.corr(audio) is None
    measured = study.metrics(audio, audio, 48000, audio)
    assert measured["stereo_correlation"] is None
    assert measured["stereo_correlation_delta"] is None
    json.dumps(measured, allow_nan=False)


@pytest.mark.parametrize("shift", [-3, 3])
def test_waveform_correlation_lag_has_known_signed_shift(study, shift):
    reference = np.random.default_rng(102).normal(0, .1, (4096, 2))
    shifted = np.zeros_like(reference)
    if shift > 0:
        shifted[shift:] = reference[:-shift]
    else:
        shifted[:shift] = reference[-shift:]
    assert study.waveform_lag(shifted, reference) == shift
    assert study.waveform_lag(reference, shifted) == -shift


def test_silent_waveform_correlation_lag_is_undefined(study):
    silent = np.zeros((4096, 2))
    nonzero = np.random.default_rng(103).normal(0, .1, silent.shape)
    assert study.waveform_lag(silent, silent) is None
    assert study.waveform_lag(silent, nonzero) is None
    assert study.waveform_lag(nonzero, silent) is None


@pytest.mark.parametrize("gain", [.5, 2.])
def test_level_matching_removes_pure_gain_without_timbre_residual(study, gain):
    reference = np.random.default_rng(104).normal(0, .1, (4096, 2)).astype(np.float32)
    altered = reference * gain
    measured = study.metrics(altered, reference, 48000, altered)
    assert measured["relative_rms"] == abs(gain - 1)
    assert measured["rms_match_gain"] == 1 / gain
    assert measured["matched_relative_rms"] == 0
    assert measured["optimal_gain_residual"] == 0
    assert measured["matched_envelope_relative_rms"] == 0
    assert measured["waveform_correlation_lag_samples"] == 0
