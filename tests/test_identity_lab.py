"""Opt-in research safeguards; unchanged production tests keep their thresholds."""
import numpy as np
import pytest

from isla.streaming import MODES, StreamingDSP
from tools.identity_lab.dsp import IdentityDSP, SHOWCASE, SWEEPS, render

FORMATS = [(44100, 1), (44100, 2), (48000, 1), (48000, 2)]


@pytest.mark.parametrize("rate,channels", FORMATS)
def test_zero_amounts_and_unselected_banks_are_exact_original(rate, channels):
    original = StreamingDSP(rate, channels)
    zero = IdentityDSP(rate, channels, {k: 0 for k in SWEEPS})
    research = IdentityDSP(rate, channels, SHOWCASE)
    rng = np.random.default_rng(730)
    for i in range(64):
        block = rng.uniform(-1.25, 1.25, (512, channels)).astype(np.float32)
        mode = MODES[i % 4]
        original.select(mode)
        zero.select(mode)
        np.testing.assert_array_equal(zero.process_block(block), original.process_block(block))
        # Bypass stays exactly delayed float32 despite warm experimental banks.
        dry = research.process_block(block)
        if i >= 3:
            np.testing.assert_array_equal(dry, previous[i - 3])
        if i == 0:
            previous = []
        previous.append(block.copy())
    assert research.delay == original.delay == 1536
    assert research.hop == 512 and research.window_size == 2048


@pytest.mark.parametrize("rate,channels", FORMATS)
@pytest.mark.parametrize("profile", tuple(SWEEPS))
def test_candidate_silence_invalid_ingress_and_state_bounds(rate, channels, profile):
    dsp = IdentityDSP(rate, channels, {profile: max(SWEEPS[profile])})
    dsp.select(profile)
    adapter = dsp.blenders[MODES.index(profile) - 1]
    shape = {k: v.shape for k, v in vars(adapter).items() if isinstance(v, np.ndarray)}
    rng = np.random.default_rng(731)
    for i in range(96):
        block = rng.uniform(-.2, .2, (512, channels)).astype(np.float32) if i < 32 else np.zeros((512, channels), np.float32)
        if i == 32:
            block[0] = np.nan
        if i == 33:
            block[0] = np.inf
        output = dsp.process_block(block)
        assert np.isfinite(output).all()
        if i > 44:
            np.testing.assert_array_equal(output, 0)
        for k, wanted in shape.items():
            assert getattr(adapter, k).shape == wanted
            assert np.isfinite(getattr(adapter, k)).all()
        assert adapter.last_energy_ratio <= 1 + 1e-12


@pytest.mark.parametrize("rate,channels", FORMATS)
@pytest.mark.parametrize("profile,amount", [(p, a) for p, values in SWEEPS.items() for a in values])
def test_candidate_near_null_perturbation_retains_original_one_percent_bound(rate, channels, profile, amount):
    n = np.arange(16384)
    for bin_index in (20, 40):
        mono = (.5 * np.sin(2 * np.pi * bin_index / 2048 * n)).astype(np.float32)
        x = np.repeat(mono[:, None], channels, axis=1)
        noise = np.random.default_rng(72).normal(0, 1e-8, x.shape)
        changed = (x.astype(float) + noise).astype(np.float32)
        amounts = {profile: amount}
        a = render(x, rate, profile, amounts)[0][4096:-4096].astype(float)
        b = render(changed, rate, profile, amounts)[0][4096:-4096].astype(float)
        assert np.linalg.norm(a - b) / np.linalg.norm(a) < .01


@pytest.mark.parametrize("profile", tuple(SWEEPS))
def test_stereo_swap_polarity_and_no_crossfeed(profile):
    x = np.random.default_rng(732).normal(0, .1, (8193, 2)).astype(np.float32)
    amounts = {profile: max(SWEEPS[profile])}
    y = render(x, 48000, profile, amounts)[0]
    swapped = render(x[:, ::-1], 48000, profile, amounts)[0]
    np.testing.assert_array_equal(y[:, ::-1], swapped)
    x[:, 1] = 0
    assert not np.any(render(x, 48000, profile, amounts)[0][:, 1])
    x[:, 1] = x[:, 0]
    mono = render(x, 48000, profile, amounts)[0]
    np.testing.assert_array_equal(mono[:, 0], mono[:, 1])
    x[:, 1] *= -1
    anti = render(x, 48000, profile, amounts)[0]
    np.testing.assert_array_equal(anti[:, 0], -anti[:, 1])


@pytest.mark.parametrize("rate,channels", FORMATS)
def test_warm_switches_equal_independent_always_running_banks(rate, channels):
    dsp = IdentityDSP(rate, channels, SHOWCASE)
    banks = [IdentityDSP(rate, channels, SHOWCASE) for _ in MODES]
    for bank, mode in zip(banks, MODES):
        bank.select(mode)
        bank.mix = np.eye(4)[MODES.index(mode)]
    previous = np.eye(4)[0]
    rng = np.random.default_rng(733)
    for i in range(48):
        x = rng.normal(0, .1, (512, channels)).astype(np.float32)
        mode = MODES[(i // 3) % 4]
        target = np.eye(4)[MODES.index(mode)]
        mix = previous[None] + dsp.fade * (target - previous)[None]
        expected = sum(bank.process_block(x) * mix[:, j, None] for j, bank in enumerate(banks))
        dsp.select(mode)
        np.testing.assert_allclose(dsp.process_block(x), expected, atol=1e-7, rtol=1e-6)
        previous = target


@pytest.mark.parametrize("profile", tuple(SWEEPS))
def test_transport_grouping_and_fresh_run_are_reproducible(profile):
    x = np.random.default_rng(734).normal(0, .1, (16384, 2)).astype(np.float32)
    amounts = {profile: SHOWCASE[profile]}
    expected = render(x, 48000, profile, amounts)[1]
    dsp = IdentityDSP(48000, 2, amounts)
    dsp.select(profile)
    padded = np.pad(x, ((0, len(expected) - len(x)), (0, 0)))
    actual = []
    position = 0
    for hops in [1, 7, 2, 3, 16, 9]:
        stop = min(position + hops * 512, len(padded))
        actual.extend(dsp.process_block(padded[j:j+512]) for j in range(position, stop, 512))
        position = stop
    actual.extend(dsp.process_block(padded[j:j+512]) for j in range(position, len(padded), 512))
    np.testing.assert_array_equal(np.concatenate(actual), expected)
    np.testing.assert_array_equal(render(x, 48000, profile, amounts)[1], expected)


@pytest.mark.parametrize("rate,channels", FORMATS)
@pytest.mark.parametrize("profile", tuple(SWEEPS))
def test_cold_step_impulse_and_subnormal_controls(rate, channels, profile):
    for kind in ("step", "impulse", "subnormal"):
        x = np.full((4096, channels), .5, np.float32)
        if kind == "impulse":
            x[1:] = 0
        if kind == "subnormal":
            x[:] = np.finfo(np.float32).smallest_subnormal
        # Leave emissions beyond the finite WOLA tail before asserting settled
        # zero; render's full-support flush ends at the tail's last sample.
        x = np.pad(x, ((0, 2048), (0, 0)))
        _, raw = render(x, rate, profile, {profile: max(SWEEPS[profile])})
        assert np.isfinite(raw).all()
        assert np.max(abs(raw)) <= .5
        assert not np.any(raw[-512:])
