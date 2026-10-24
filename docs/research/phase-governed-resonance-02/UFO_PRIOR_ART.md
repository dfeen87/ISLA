# ISLA Experiment 02: U.F.O. applicability and established DSP

Assessment date: 2026-10-24. Scope: read-only inspection of the authoritative U.F.O. repository, two primary U.F.O. PDFs, its current mathematical conformance records, selected executable modules, and primary DSP sources. No U.F.O. repository state, branch, or publication was changed. This document is a research assessment, not evidence that a candidate audio processor has passed its gates.

## Provenance and source hierarchy

The connected GitHub account lists **dfeen87/UFO**, whose default branch is `main`. At inspection, `main` resolved to **da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d**, committed 2026-10-09, merge PR #57. All U.F.O. references below are pinned to that commit. The repository identifies its active technical release as 5.0.0. Its README also records unresolved executor isolation/retry issues and does not authorize v6; this is relevant to avoiding any inference that an agentic simulation is suitable inside an audio callback. [Pinned repository](https://github.com/dfeen87/UFO/tree/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d), [README](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/README.md).

The repository's index records 11 PDF filenames representing 10 unique documents. `Publication Dynamic Radial Membrane.pdf` is an alias of `A Governed Deformable Radial Membrane.pdf`. The present assessment directly read the latter and `Unified Math in U.F.O.pdf`, rather than claiming every paper was independently examined. The two PDFs were retrieved from the pinned public raw URLs after the GitHub connector's binary limitation; relevant equations in Unified Math pp.12-13 were visually checked after rendering. [Paper index](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/README.md).

| Downloaded source | Pages | SHA-256 |
|---|---:|---|
| Unified Math in U.F.O.pdf | 18 | `a0cf4b025e19290070f13542a690ce4edfaaecef459a85a729577ac045145b00` |
| A Governed Deformable Radial Membrane.pdf | 23 | `af0c803d93cc04496fae762bac86a5bbd712592e76dd0a17597b9cf3e733e9c7` |

The PDFs define the research claims. Executable code defines actual operations. The v4 traceability and v5 conformance records explicitly distinguish proofs from regression evidence and identify approximation, naming overload, and unimplemented research. They must not be replaced by the README's more ambitious descriptive language. [Traceability](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/PAPER_IMPLEMENTATION_TRACEABILITY.md), [v5 conformance](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/V5_MATHEMATICAL_CONFORMANCE.md).

## Actual U.F.O. mathematics and defensible reuse

### Constrained successor selection: applicable as architecture

*Unifying the Math in the U.F.O.: A Technical Note on Pythagorean Projection*, printed p.12, section 17, gives the following unnumbered rule:

`x(t+1) = argmin_{x' in S_safe} [ E(x',t) + lambda_C C(x',t) + lambda_F F_route(x,x') - lambda_Q Q(x',t) - lambda_T Delta_task(x',t) ]`.

The paper defines `S_safe` before optimization as policy-, safety-, and compute-valid candidate states. Its state is an AI behavioral membrane, and its costs/coherence/task values are not audio metrics. The strongest justified transfer is **admit a bounded processing candidate before committing its control/state change**. ISLA may independently define a safe control domain and evaluate candidates or use transparent deterministic rules. An audio objective requires separately registered, normalized distortion, attack, beating, stereo, and musical target terms. This is a documented adaptation of a constrained-selection pattern, not a newly discovered DSP law and not proof that the audio problem has an equivalent objective. [Primary PDF, p.12, section 17](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/papers/Unified%20Math%20in%20U.F.O.pdf).

### Closure and projection: exact formulas, no automatic audio semantics

The same PDF p.1 section 2 and p.10 section 12 defines `i=(a^2+b^2)/c^2`. On p.9 section 10, the residual is `rho=A-Pi_G(A)` and governed velocity is `(Pi_G(A)-x)/Delta_t`. Runtime `projection.py` lines 15-44 tests closure with a floating-point tolerance; lines 47-86 perform radial Euclidean projection when capacity is exceeded: `(a,b) -> c(a,b)/sqrt(a^2+b^2)`. Capacity near zero fails closure and returns zero projected legs. The weighted path is separately implemented. [Projection source](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/projection.py#L15).

These formulas require compatible dimensions and a justified orthogonal/Euclidean state representation. ISLA's attack damage, spectral novelty, stereo correlation, and beating damage are not automatically orthogonal lengths. Applying the circle formula to arbitrary normalized features would be a newly chosen controller geometry requiring its own validation. It would not establish physical conservation, resonance protection, or acoustic stability. Ordinary interval clamps and explicitly independent safety limits are sufficient unless a joint geometry earns its complexity. `angular` and `radial` labels in the runtime intentionally alias Euclidean rescaling; the v5 conformance record rejects an invented distinct metric theory.

### Temporal trace: real published recurrence, explicitly incomplete runtime

Unified Math p.13 section 17 gives:

`B(theta,t+1) = rho_B B(theta,t) + epsilon_B [Delta_R(theta,t)+Delta_C(theta,t)+Delta_tau(theta,t)+Delta_kappa(theta,t)]`, with `0 <= rho_B < 1`.

Its variables describe changes in membrane geometry, cost, tension, and stiffness. The text characterizes a fading short-horizon imprint. The v5 conformance record explicitly says no dedicated runtime state implements the complete equation. `admissibility.boundary_loop_trace()` is a sampled **polar arc length**, not this temporal memory. A DSP envelope/memory controller can use an ordinary leaky recurrence, with independently defined audio units and bounded stimulus, but should not claim to import a complete proven U.F.O. memory mechanism. [Primary PDF, p.13](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/papers/Unified%20Math%20in%20U.F.O.pdf), [runtime distinction](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/admissibility.py#L210).

`temporal.py` provides separately implemented bounded deques (lines 36-47), exponential averages (88-112), accumulated tension (125-154), and decay (170-184). The EMA is `v_bar[n]=eta v_bar[n-1]+(1-eta)v[n]`. The accumulator is `T[n+1]=gamma T[n]+stimulus[n]`. Crucially, runtime validation permits `gamma=1`; repeated positive stimulus can therefore accumulate indefinitely. This is not an audio-tail stability guarantee. An audio adaptation needs a strict decay factor below one, bounded input/state, reset rules, and a finite residual-history policy. Converting a desired time constant to `eta=exp(-H/(Fs*tau))` is standard discrete DSP, not an invention attributable to U.F.O. [Temporal source](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/temporal.py#L36).

### Three distinct meanings of phase

U.F.O.'s twelve fixed behavioral positions `theta_i=2*pi*i/12` and angular membrane basis are specified in Unified Math p.10 section 11. V-channel angular alignment on p.11 section 13 is `(1+cos(theta_i-theta_j))/2`; the executable `channels.phase_alignment` is a local behavioral routing weight. This is not a piano string phase model. [Channel source](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/channels.py#L22).

The function called `phase_smoothing`, `admissibility.py` lines 184-207, takes a circular sliding average of the **activation values of the twelve behavioral strings**. It does not unwrap or modify Fourier phase angles. Likewise, a musical attack-to-sustain transition is an estimated acoustic regime change; it is not an angle in radians. The controller must maintain separate data types, clocks, units, and names for Fourier phase, acoustic state, and processing permissions. [Actual smoothing implementation](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/admissibility.py#L184).

### Energy and stability: no transferable theorem

Unified Math p.12 section 16 defines `V=C_total+alpha sum(r_i-r_bar)^2+beta sum(tau_i)+gamma sum(kappa_i)` with desired `Delta V<=0` absent task expansion. The runtime instead documents `sum(alpha*r_i^2+beta*c_i+gamma*tau_i^2)` in `governor.py` lines 277-295. These are not identical equations. The repository's audit limits the tested result to a restricted no-pressure non-increase, often equality; it claims no positive definiteness, strict decay, or global asymptotic stability. Neither quantity is physical audio energy. Audio safeguards must measure actual samples, energy, gain, tails and peaks. [Governor source](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/radial_membrane_ai/governor.py#L277), [conformance boundary](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/docs/V5_MATHEMATICAL_CONFORMANCE.md).

### Agentic machinery: use for evidence handling only

The current `UFO.md` specification and v5 conformance distinguish proposal from admission, diagnostics from authorization, provisional observations from durable memory, and previous-cycle evidence from permission for the next action. These patterns are useful for auditable offline experiment ledgers and fail-closed validation. There is no reason to run an agentic planner, tools, LLM, trust-memory subsystem, or model inference in ISLA's deterministic audio path. [Current v5 specification](https://github.com/dfeen87/UFO/blob/da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d/UFO.md).

## Established DSP controls and references

### Phase vocoder, transient protection and stereo

Laroche and Dolson, *Improved phase vocoder time-scale modification of audio*, IEEE TSAP 7(3), 323-332 (1999), DOI 10.1109/89.759041, is established prior art for phase coherence and identity phase locking. The publisher page was robot-gated in this session, so do not claim an independent full-text review of that particular paper. The authors' later primary paper and Ravelli et al. discuss the same phase-vocoder lineage. [Publisher reference](https://ieeexplore.ieee.org/document/759041), [Laroche/Dolson author paper](https://www.ece.uvic.ca/~peterd/48409/Dobson1999.pdf).

Ravelli, Sandler and Bello, DAFx 2005, *Fast implementation for non-linear time-scaling of stereo signals*, section 2 equations (1)-(5), states STFT analysis, instantaneous-frequency propagation, and IFFT/overlap-add. Its section 3 protects transient regions through nonuniform time scaling. Section 4.3 synchronizes onset treatment across stereo channels and uses short-time cross-correlation discrepancy, equation (8), to assess stereo damage. Independent channel onset schedules can shift alignment and move the image. Its finite test results are not universal guarantees. For ISLA, a common time map, common transient decisions and explicit interchannel-phase policy require stereo fixtures and actual measurements. [Primary paper](https://www.dafx.de/paper-archive/2005/P_182.pdf).

Implementation assumption: preserving per-bin `phi_L-phi_R` via a common phase correction is an explicit stereo policy, not a guarantee of unchanged reconstructed stereo. Window overlap, phase locking, resets and unreliable/silent bins still need tests. Similarly, identity phase locking preserves phase relations within spectral peak regions; it does not prove retention of two physically separate partials that the analysis window cannot resolve. The required 1.25 and 1.50 duration factors are modest tests, not reasons to skip attack, pitch or stereo gates.

### Onsets and detector ambiguity

Duxbury, Bello, Davies and Sandler, DAFx 2003, *Complex domain onset detection for musical signals*, equations (4)-(5), predicts constant phase advance; equations (7)-(11) predict each bin using previous magnitude and `2*phi[n-1]-phi[n-2]`, then sum complex Euclidean prediction errors. The paper separately discusses detection functions and peak picking, and notes noisy/overlapping limitations. This supplies an independent spectral-novelty view rather than equating a selected envelope maximum with a note's physical beginning. [Primary paper](https://www.dafx.de/paper-archive/2003/pdfs/dafx81.pdf).

Dixon, DAFx 2006, *Onset Detection Revisited*, section 1 and section 3.1, distinguishes physical and perceived timing and explains ground-truth limitations. A spectral detector's accepted event window is not an acceptable audio-processing displacement tolerance. The paper compares methods on 1060 general onsets and 106054 piano onsets; ISLA cannot infer that coverage from one recording. [Primary paper](https://www.dafx.de/paper-archive/2006/papers/p_133.pdf).

Boeck and Widmer, DAFx 2013, *Maximum Filter Vibrato Suppression for Onset Detection*, equations (5)-(6), applies a frequency-axis maximum filter to a prior log-frequency spectrum before rectified spectral differences. Its peak picker uses separately declared windows and a threshold. This is a suitable conventional independent detector and a reminder that natural modulation can generate false detections. It is not a proven piano-beating classifier. [Primary SuperFlux paper](https://www.dafx.de/paper-archive/2013/papers/09.dafx2013_submission_12.pdf).

The official librosa 0.11.0 docs provide reproducible controls. `onset_strength` computes rectified spectral flux against a maximum-filtered reference; default `max_size=1` **disables** that filter. The official Superflux example uses `lag=2`, `max_size=3` and a Mel approximation to the paper's log-frequency representation. Label that approximation. `onset_detect(backtrack=True)` moves detected peaks to preceding minima for segmentation; it does not independently locate a physical hammer strike. Freeze frame centering, hop and time conversion. [onset_strength](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_strength.html), [Superflux example](https://librosa.org/doc/0.11.0/auto_examples/plot_superflux.html), [onset_detect](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_detect.html).

Recommended Experiment 01 investigation: establish event neighborhoods from the original source, preserve both top-ranked near-equal peaks, compare local waveform lag, energy-rise/slope timing, complex novelty and Superflux, then audition. A peak-rank flip with near-zero waveform lag supports detector ambiguity but does not establish harmlessness. Preserve unresolved disagreements. Any recorded-source event time remains an estimate unless an independent physical annotation exists.

### Piano beating, decay and inharmonicity

For a controlled two-tone fixture, algebra gives:

`cos(2*pi*f1*t)+cos(2*pi*f2*t)=2*cos(pi*(f1-f2)*t)*cos(pi*(f1+f2)*t)`.

The signed multiplier changes sign; audible amplitude maxima recur at `abs(f1-f2)`, not half that rate. More generally, for positive-frequency components, `abs(z)^2=A1^2+A2^2+2*A1*A2*cos(2*pi*(f1-f2)*t+Delta_phi)`. Damped amplitude factors may vary with time. These are exact synthetic interference controls, not a full coupled piano model.

Julius O. Smith's author-hosted *Physical Audio Signal Processing*, Coupled Strings, explains why slightly detuned string sums can approximate beating but cannot by themselves reproduce true two-stage coupled decay. Bridge-mediated coupling matters. Natural modulation and aftersound therefore belong among the retained signal characteristics. [Stanford CCRMA source](https://ccrma.stanford.edu/~jos/pasp/Coupled_Strings.html). Weinreich's original *Coupled piano strings*, JASA 62(6),1474-1484 (1977), DOI 10.1121/1.381677, is a foundational reference; its full text was not accessible here, so no exact equation from it is claimed.

Gracia and Sanz-Perela derive pinned stiff-string spectra in *The wave equation for stiff strings and piano tuning*. Keep frequency conventions explicit: `f_n=n*f_ideal*sqrt(1+B*n^2)` uses the ideal flexible-string fundamental; using the actual first partial instead gives `f_n=n*f_1*sqrt((1+B*n^2)/(1+B))`. Do not accidentally move the fixture's specified first partial. The model is an idealized stiff string and does not supply soundboard/coupling realism. [Author preprint](https://arxiv.org/abs/1603.05516).

## Recorded piano license recheck

The current authoritative source page for **Emotional Piano by triangelx**, Freesound sound 189175, was accessible on 2026-10-24. It explicitly displays **Creative Commons 0**, with 16.000 seconds, stereo WAV, 44.1 kHz, 16-bit, uploaded May 23, 2013. The pre-existing local file identity supplied by the main experiment is SHA-256 `9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15`. The page does not expose a matching SHA-256, so this source-page recheck confirms the license label and metadata; local byte integrity must be checked separately against the preserved Experiment 01 manifest. [Authoritative sound page](https://freesound.org/people/triangelx/sounds/189175/).

## Disposition

**U.F.O. applicability: limited, explicit architectural adaptation is justified.** Safe-domain-before-selection, bounded histories, atomic candidate validation, residual logging and replayable evidence are useful design patterns. Its actual constrained successor objective is a legitimate citation. Importing behavioral angles as Fourier phases, treating membrane energy as audio energy, turning arbitrary damage metrics into orthogonal legs, or claiming a stability theorem is unsupported. Use ordinary deterministic DSP where it provides the mechanism more clearly. Acoustic benefit, audible distinction and creator preference remain separate empirical gates; none is established by this literature inspection.
