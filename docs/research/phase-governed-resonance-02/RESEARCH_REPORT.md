# ISLA Musical Identity Lab · Experiment 02
## Phase-governed resonance · Scientific research report

October 24, 2026. Research status: **REVISE / INCONCLUSIVE; no production promotion**.

The experiment produced functioning, separately testable Velvet, Legato and Melt
adapters, a deterministic acoustic-regime controller, an offline stereo phase
vocoder, numerical evidence, recoverable source code and creator listening files.
The three governed identities passed the registered **hard numerical screens**
on the tested inputs. Fixed and shuffled controls passed those same screens.
Consequently, these results do **not** establish superiority of transition
governance, audible improvement, a preferred identity, or a novel DSP invention.
Creator listening is pending. Robust slowdown remains incomplete because two
unchanged impulse-timing tests fail.

### Authority, production protection and preservation

The authoritative inspected main is `20a32de76396ab3400f14c5169276d6f03b72d08`.
Published v3.1.1 is `3621f782d3f93334a68b7a82a3ff7ad451003ead`.
Remote main was rechecked after evaluation and remained at that commit. Before
research publication, main was the only remote branch and there were no open
PRs. The creator's classical-piano inspiration appears in current README.
No production audio, routing, metadata, version, or published tag was changed.
The source commit delivered with the package is in RESEARCH_COMMIT.txt; the
premeasurement implementation/protocol commit is
`07a234360e65bb5ca5dc61130d0a7116b59c008a`.

Actual streaming DSP still has 2048-sample frames, 512-sample hops, 1536-sample
delay, periodic Hann double-window WOLA with primed startup weights, original
.35/.55/.75 banks, 5 ms mode selection fades and a separate exact delayed
Bypass. Offline BEDROCK and LIVE are different paths. The native C++17 JUCE
plugin embeds Python through pybind11 and invokes IslaBuffer; it is not the new
research controller. Native configuration cannot complete because both vendored
dependency folders contain only .gitkeep files. This is a baseline dependency
blocker, not a newly validated native build or an audio callback guarantee.

Experiment 01's deleted remote branch survives at exact local commit
`2be4668b9661ed931222dca09dabcb9739624b4a`. Preservation verified all 877
non-cache logical files, 388 unique original files (416,861,333 bytes), published
artifact hashes, internal manifests, protected source hashes, 298 tracked
research blobs and 1,232 original Git objects. Four dangling blobs were exported.
A new self-contained bundle restores independently; the original published
incremental bundle and its prerequisite were retained. Original files and refs
were not changed. A separate preservation commit/PR is unnecessary because the
committed source and full history are recoverable. See the sibling
Experiment-01-preservation package, whose manifest SHA256 is
`992c3c66fd184b0b48fb62348510148cdd9a65bdcc355d2f4aa04cdd2d26d429`.
A second independent device/cloud backup is recommended and has not been made.

### What was implemented

SPECIFICATION.md gives equations, units, numerical floors and reset policies.
The five features are energy, positive spectral flux, power-flatness structure,
causal previous-frequency phase prediction and bounded magnitude memory. Six
normalized operational weights describe attack, bloom, sustain, decay, overlap
and silence. They are processing categories, not identified individual notes.
Ambiguity and confidence are logged. New attacks, insufficient confidence and
silence veto processing; a time-based slew governs recovery.

Velvet uses protected log-magnitude **frequency curvature** with a smooth 3 kHz
weight. Legato uses 80 ms **temporal magnitude history**, supported-bin gating
and a +1.5 dB per-bin ceiling; it cannot extend a note into exact silence. Melt
uses a distinct **bounded instantaneous-frequency/phase-trajectory correction**
(±.10 rad, above 500 Hz), rather than renaming either magnitude operation.
All controls are deterministic; stereo shares a magnitude gain or phase offset.
Pre-WOLA stereo phase invariance is tested separately from output reanalysis.
There is no hidden normalizer, limiter, cloud inference or LLM in DSP.

The equations were treated as starting hypotheses. Important deviations are:
newest-hop energy avoids redundant overlap energy; current-magnitude denominator
floor stabilizes flux at silence; the chosen fixed rule controller replaces an
unnecessary optimizer; Melt uses bounded phase correction; discontinuity handling
is explicit independent-segment reset rather than a LIVE stream integration.
Immediate safety veto overrides ordinary slew and is explicitly logged.
An early Melt reliability-mask carryover defect was fixed and tested **before**
freezing. Independent review also fixed muted-output screen blindness, undefined
stereo correlation, correct one-sided Parseval weighting and the fixed-history
control's accidental attack reset before candidate evaluation.

UFO_PRIOR_ART.md pins U.F.O. main
`da4eb5f4a96b29bb0e34a8ac2a89dc695764cd2d` and actual paper/source references.
The actual safe-domain-constrained successor selection supports an architectural
admission/veto analogy. Its behavioral phase, heuristic energy and state-space
geometry are not validated acoustics. An unbounded-accumulation edge in one
U.F.O. memory rule is specifically unsuitable for direct audio reuse. No claim
equates Fourier phase, musical regime and governance. Standard EMA conversion
and phase-vocoder equations are recognized prior art.

### Frozen design and evidence

The primary FREEZE.json SHA256 is
`0d41467f483776a3ed4ac260d7c38068c9a52cc2b34deacb0b63c0f7b60ecd79`. It records 40 code/protocol
hashes, all default parameters, source-manifest hash and dependency versions.
Code, acceptance limits and candidate settings were not changed after evaluation.
Primary grid: 3 identities × 6 governed/fixed/matched/attack/shuffled/noop
variants, 3 original production banks, 3 recovered Experiment 01 adapters,
exact Bypass and a conventional scalar-envelope comparison: 26 labels total.
There was no retrospective parameter winner selection.

All 56 reused Experiment 01 source/format cells match their original float32
audio hashes. Four additional cells use seconds 9–15 of the same recorded piano;
16 long beating cells use 440/3520 Hz carriers, Δf=.2/1/1.5/3 Hz and either no
damping or τ=6 s. There are 76 cells and 1,976 records.
The six-second recorded study excerpt is seconds 2–8 plus .125 s guards.
Emotional Piano by triangelx is labeled CC0 on the verified original Freesound
page; source SHA256 is
`9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15`.
The reserved excerpt is from the same artist/instrument/source; it is not an
independent recording or evidence of broad classical-piano generalization.
The source author labels it piano; acoustic versus sampled instrument and
recording technique remain unverified.
Generated piano-like fixtures are mathematical additive models, not real pianos.

### Main numerical findings

| Governed identity | Hard-screen failed cells | Cells with unresolved attack flags | Max beat-frequency error (Hz) | Min detrended beat-envelope correlation | Max damped τ error | Max stereo IPD RMS change (rad) |
|---|---:|---:|---:|---:|---:|---:|
| Velvet | 0/76 | 27 | 0.0000141 | 0.999777 | 0.127% | 0.00159 |
| Legato | 0/76 | 26 | 0.0000125 | 0.997661 | 0.172% | 0.00976 |
| Melt | 0/76 | 27 | 0.0000046 | 1.000000 | 0.060% | 0.00895 |

All reported maxima/minima refer to applicable tested cells, not universal
guarantees. Beating-frequency and independently fitted two-frequency spacing
are separate fields in each record; neither interprets a short FFT bin as an
isolated partial. Low/high carriers remain separately available. The beating
envelope may change slightly; preserving every sample was not forced. New
governed sample/4× peak maxima remain below .98; the largest 4× value among the
three governed modes is 0.674093.
The estimate is not a certified true-peak measurement. Original-duration known
tone pitch, settled silence, gaps and hard attack timing/energy screens pass
for the governed variants. Exact Bypass and three noops are bit-identical.

**Governance has not earned its complexity on these results.** All governed,
fixed, fixed_matched, attack_gated and shuffled variants have zero hard failures.
The reference input itself has 27 cells with ambiguous attack detector evidence;
similar governed counts cannot automatically be attributed to processing.
CONTROL_COMPARISON.md reports paired descriptive effects and all ablations.
Equal nominal control depth does not equal equal waveform transformation:
Legato/Melt matched-control comparisons remain confounded by actual effect size.
No claim that a smaller residual proves musical continuity is made.

Legato's connected-melody envelope-roughness ratio has four-format median
1.000340 (a slight increase), compared with .935099 for fixed history,
.979508 for fixed_matched and .979816 for the scalar-envelope control. The
governed path therefore does not improve that registered numerical continuity
proxy. This does not determine creator judgments of musical connectedness.

At 48 kHz stereo, governed waveform residual RMS relative to input on the known
piano crop is approximately Velvet .137%, Legato 1.360%, Melt .821%; on the
reserved crop it is .121%, 1.544%, .477%. These quantify change, not audibility.
The small changes may prove inaudible or musically irrelevant. Registered
continuity-envelope proxies, processing percentages, control depth, veto/limit
counts, confidence, regime transitions, phase errors and resource use are all
available per record. Novelty from extra parameters is not inferred.

Conventional envelope control fails 12 new research-screen cells; original
production Melt fails 18 and Experiment 01 Melt .30 fails 20. These are stress
screens relative to original input under new criteria and corpus, **not** a
production regression or a rewrite of Experiment 01's original conclusions.
Every failure is retained in metrics.jsonl and the complete label summary.

The primary run took 423.1 s including metrics, file output
and listening preparation, with observed process peak RSS
959.9 MB on this Mac. Per-label render-only time
excludes cached state analysis and metrics. The offline implementation caches
full-file spectra/frames; total memory scales with input duration. This is not
a bounded-memory streaming implementation or a real-time performance claim.

### Historical attack failures and estimator limits

All six selected Experiment 01 failure cells reproduce their original and
candidate hashes and original detector offsets exactly. The six discrepant
events retain approximately 10.1–17.2 ms envelope-peak disagreements. Independent
local waveform NCC finds lag 0 samples, with NCC .999076–.999998; independent
novelty-peak shift is 0, while fixed 10 ms energy movement is −.010 to −.738 dB.
The evidence supports competing-peak ranking rather than a demonstrated physical
signal delay. Every original FAIL and unresolved flag remains preserved; zero
lag is not a perceptual clearance. Direct listening is still required.

STFT features do not prove polyphonic note identity or physical hammer timing.
Flatness can mischaracterize bass/chords/noisy recordings. Phase reliability
and confidence are engineering proxies. The additional ESTIMATOR_AUDIT, if
present, compares against established librosa onset detection and known synthetic
events; it is explicitly post-freeze diagnostic evidence, with no parameter
retuning or retroactive preregistered claim.

That audit matches 124/128 known synthetic events within its stated 25 ms
diagnostic tolerance, versus 128/128 for the established reference. Both 0.2 Hz
beat fixtures produce six attack-evidence peaks despite a single excitation.
This directly demonstrates that natural interference can fool the controller;
the architecture does not reliably distinguish every new note from beating.
Recorded detector agreement has no physical-strike ground truth. These findings
argue for revising the estimator before any production proposal.

### Offline slowdown: functioning prototype, incomplete gate

The raw and protected stereo-shared vocoders implement established phase
propagation, optional identity phase locking and a heuristic transient reset.
Ratios 1.25/1.50 give exact target sample counts. Raw/protected untreated files,
protected+each identity, and an established librosa independent-channel reference
produce 48 WAVs. All duration counts verify. Stationary tone pitch is very close
to original, but this does not prove pitch transparency on arbitrary piano.

The two strict 16 kHz development impulse tests fail: protected maximum event
errors 14.5 ms (1.25) and 29 ms (1.50) exceed the frozen 10 ms limit. Raw 1.50
also duplicates events in that fixture. The separate 48 kHz impulse fixture has
smaller errors; it does not erase these failures. Supplemental mapped-frame
stereo analysis finds substantial piano IPD changes even with shared synthesis
phase offsets. Stationary coefficient integrity is therefore insufficient to
establish transient/stereo transparency. SLOWDOWN.md and the supplemental audit
expose exact definitions, phase/smear/pitch/peak results and alignment assumptions.
There is no LIVE integration and no claim of novel time stretching.

### Listening and decisions

The primary package contains 40 randomized A/B trials, hidden A/A controls,
separate answer key, 104 labeled raw original-duration WAVs and 48 labeled
slowdown WAVs. Separate post-freeze direct cross-mode comparisons, if present,
address distinctness without retuning DSP. Raw FLOAT WAVs preserve actual level;
listening copies apply only logged scalar RMS matching plus common peak headroom.
The complete prepared listening set has 40 primary, 12 direct cross-mode and
12 slowed-piano paired trials (64 total). The additional comparisons were
prepared after the freeze using saved WAVs; they do not retune DSP or overwrite
the primary key. Slowed pairs compare protected untreated stretch with that
same stretch followed by each identity, independently of the duration study.
This is not certified equal perceptual loudness. Eight independent response
questions remain blank. No creator hearing, preference or artifact judgment has
been fabricated. Browser playback is not accepted as DSP verification.

| Question | Disposition |
|---|---|
| Velvet musical identity | INCONCLUSIVE — safe tested prototype; audible softness/preference pending |
| Legato musical identity | REVISE — continuity proxy does not improve; connectedness and attack preference pending |
| Melt musical identity | INCONCLUSIVE — distinct phase mechanism; perceptual resonance/identity pending |
| Added governance complexity | REVISE — no binary safety-screen advantage; effect-dose confounds and false onsets |
| Robust offline slowdown | REVISE — frozen transient failures and piano stereo changes remain |
| Production promotion | REJECT for this pass — research evidence and creator acceptance incomplete |

Production-promotion rejection is a scope/readiness decision, not rejection of
the creator's artistic hypothesis. No automatic merge, version bump or release
is authorized or performed. A future experiment should first collect blinded
creator responses, then develop genuinely effect-matched fixed controls and
broader independently licensed classical-piano recordings. Any retuning must
receive a new freeze; failed primary evidence must remain available.

### Regression, reproducibility and preservation

Production baseline: 305 passed, 1 unchanged expected failure. Final combined
suite: **418 passed, 2 slowdown failures, 1 unchanged expected failure**. The
red slowdown tests remain red; no xfail or limit relaxation was introduced.
Development corrections and sandbox/socket/dependency setup failures are retained
separately from final test results. The native dependency blocker is documented.

REPRODUCE.md describes source-bundle restoration, dependency setup, checksum
verification, exact-input replay and intentionally red checks. The self-contained
Git bundle and source archive include all small research code/docs. Large WAVs,
states, metrics and generated datasets remain outside normal Git. Manifest
verification and a test restore accompany the package; these local copies are
not a second independent backup. Keep both experiments on separate storage and
verify their manifests before relying on the backup.
