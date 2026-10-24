# Experiment 02 · Phase-governed resonance

Research-only offline adapters. Production baseline is main
`20a32de76396ab3400f14c5169276d6f03b72d08`; published v3.1.1 is
`3621f782d3f93334a68b7a82a3ff7ad451003ead`. No production module imports this lab.

## Physical scope and representation

For two nearby tones, cos(2πf₁t)+cos(2πf₂t) =
2cos(π(f₁−f₂)t)cos(π(f₁+f₂)t). Absolute envelope is
2|cos(πΔft)| with repetition 1/Δf seconds. Damped fixtures multiply by
exp(−t/τ), τ=6 seconds. Δf is .2, 1, 1.5 or 3 Hz. This is a beating reference,
not a coupled-string piano model. The Fourier resolution of a 2048-point frame
at 48 kHz is 23.4375 Hz: these components are deliberately unresolved in an
individual frame. Long-record frequency fitting, not bin labels, measures them.

X_c[n,k]=Σₘx_c[nH+m]w[m]exp(−j2πkm/N), A=|X|, φ=arg X,
ω_k=2πk/N, f_k=k f_s/N. N=2048 samples, H=512 samples, Δt=H/f_s seconds.
Periodic Hann analysis AND synthesis windows use pointwise sum-of-squared-window
normalization. Virtual left padding N−H and right flush preserve full support;
crop N−H samples after reconstruction. The retained region has nonzero overlap
weights. No-op reconstruction is tested independently; exact Bypass/no-op
adapters return a copy of the original samples without an FFT round trip.

The research analysis is causal in **frame order**, but frames see their whole
support. Center labels are not physical event timestamps and this offline API
does not establish LIVE latency. Production's verified 1536-sample delay and
5 ms mode crossfade remain unchanged. Production banks use .35/.55/.75 strengths,
primed Hann-squared startup weights, shared phase reference and exact delayed dry.

## Features and uncertainty

Magnitude pooling p[n,k]=sqrt(mean_c A²). Analysis band is 80–12000 Hz.
Newest nonoverlapping hop RMS E and log change d=log(max(E,10⁻⁵)/max(Eprev,10⁻⁵))
avoid redundantly summing overlapping frame energy. Energy units are normalized
sample amplitude. O=Σpositive(p−pprev)/max(Σpprev,.05Σp,10⁻¹⁰), band-limited.
The .05 current-frame denominator prevents divergence after silence. It does
not validate a detected event as a physical strike.

T=1−spectral_flatness(power), clipped [0,1]. The additive power floor is 10⁻²⁰.
Flatness is a structure proxy and cannot identify piano notes or harmonic truth.

r=principal(φ−φprev−ωH), ν=ω+r/H (radians/sample).
Prediction error e=principal(φ−φprev−Hνprev) uses previous-frequency prediction,
not a frequency fitted from the current error. principal returns [−π,π).
Reliable bins must exceed 10⁻³ of each channel's frame maximum and absolute
10⁻⁷ magnitude in both adjacent frames, inside the analysis band.
q=min(A,Aprev)² on reliable bins; C=Σq cos(e)/max(Σq,10⁻¹⁰).
Confidence h=T max(0,C), or zero with no reliable bins or silence.
This is an engineering confidence proxy; interchannel integrity is measured separately.

Magnitude history R=ρRprev+(1−ρ)p, ρ=exp(−Δt/τ), τ=.02 s at strong attacks and
.18 s otherwise. Both newest-hop and full-frame RMS below 10⁻⁵ clear history.
This threshold is −100 dBFS, a declared conservative noise-floor policy. It
deliberately prevents synthesizing tails out of near-silence. No individual
notes are separated. Silence/discontinuities reset histories; rendering separate
segments implements explicit discontinuity reset, without reconstructing lost sound.

## Operational regimes and rules

a=clip(max(O/.35,d/log(2)),0,1). A 35% spectral replacement or doubling of RMS
in one hop requests full attack protection. These are fixed engineering
assumptions, not learned auditory thresholds. Time since a≥.5 drives
b=exp(−time/.12 s)(1−a). Decay evidence v=clip(−d/(3Δt),0,1) spans log-amplitude
slopes down to −3/s. Overlap evidence o=a·I(Rsum>.25 psum)·I(history active).
Raw regime weights are [a,b,h(1−v)(1−b)(1−a),v(1−a),o,0]. Normalize their sum
to one; silence overrides to [0,0,0,0,0,1]. If all nonsilent scores vanish,
use the sustain operational label with zero confidence, hence dry fallback.
All six weights are reported, including ambiguity via 1−max(g) and entropy.
An overlap label alongside attack evidence does not authorize blurring the new attack.

Targets: uV=.16 h(1−a)(gS+.5gB+.3gD),
uL=.30 h(1−a)(gD+gO), uM=.30 h(1−a)gS.
Control increases/decreases by at most umax Δt/.10 s per frame, bounded [0,umax].
Attack a≥.5, silence, or h<.2 immediately veto governed processing (u=0).
This safety veto deliberately overrides the slew bound; WOLA distributes the
change over overlapping frames. Its waveform consequences are measured rather
than assumed click-free. There is no dwell-time claim or hidden optimizer.

Fixed variants remove state dependence except silence, including disabling
attack-driven history resets in Legato/Melt. fixed_matched uses the
mean **input-derived** governed target on active frames, attack_gated uses
umax(1−a), and shuffled permutes the target with seed 20261024 while retaining
the independent attack/silence/confidence veto. The matched target is not
post-output tuning and may differ from actual governed depth due to slew/veto;
both actual depths are reported. A no-op governance control returns exact input.

## Three distinct mechanisms

**Velvet**: L=log(max(p,10⁻¹⁰)), K=L[k−1]−2L[k]+L[k+1], boundary K=0.
W=f²/(f²+3000²). M=0 in unsupported bins, .25 on local magnitude maxima,
1 otherwise. Shared gain exp(uV W M clip(K,−1,1)). Positive curvature fills
valleys, negative curvature attenuates peaks; the protected-peak mask tempers
the latter. This diffusion sign is verified with a three-bin example. No
claim that this proxy measures warmth or perceptual harshness.

**Legato**: L-history=ρL-history_prev+(1−ρ)L, ρ=exp(−Δt/.08 s).
At attacks and silence reset history to current L. Shared gain
exp(uL support clip(L-history−L,−.6,.6)). This temporal magnitude trajectory
operation may add positive gain. It adds no unsupported bins and no waveform
tail at silence; it can only reshape existing supported energy. Its memory is
finite-valued exponential history, with reset and bounded residual contribution.
This is not literal note extension. A conventional asymmetric scalar-envelope
follower with the same +1.5 dB ceiling is an additional comparison.

**Melt**: track instantaneous angular frequency with .06 s EMA. Define
δν=Σ_c q(νtrack−ν)/max(Σ_c q,10⁻¹⁰),
ψ=clip(exp(−Δt/.08 s)ψprev+uM Hδν,−.10,.10) radians.
Only supported reliable trajectories above 500 Hz receive the shared phase
offset; DC/Nyquist remain real and unmodified. Y_c=X_c exp(jψ).
This is bounded temporal phase correction, distinct from either frequency
diffusion or magnitude-history interpolation. Its intended sustained-resonance
effect is a hypothesis; a weak or inaudible change counts against complexity.
Attacks and silence reset ψ. Stereo uses one offset, not independent synthesis
phases. Exact pre-WOLA interchannel phase conservation is not a proof of
post-WOLA stereo transparency; both are separately checked.

All magnitude operations clamp common gain to [.80,1.188502227] (−1.94,+1.5 dB).
No per-frame global normalization or limiter is applied. These per-bin limits
do not bound arbitrary reconstructed sample/intersample peaks. Explicit output
peak screens can reject a render. Listening gain is separately logged.

## Governance and U.F.O.

This experiment uses transparent rule-based admission/veto, bounded history and
rate-limited control. No runtime optimizer or λ-weighted objective is implemented;
therefore no unsupported normalization or fitted λ is presented as evidence.
U.F.O.'s actual constrained successor equation is documented in UFO_PRIOR_ART.md.
Its safe-domain-before-selection structure informs the veto, not the acoustic
feature definitions. Fourier phase, operational regimes and governance are
three distinct concepts. No LLM, cloud service or autonomous agent runs in DSP.

The elementary offline vocoder is documented separately in SLOWDOWN.md. Its
ratios 1.25/1.50 are an independent factor. Original-duration identity results
remain primary and are never inferred from stretched sound alone.
