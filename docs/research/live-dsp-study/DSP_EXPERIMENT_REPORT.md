# DSP experiment report

ISLA — SOL ULTRA · V3.0 · October 24, 2026

**Decision: MORE EVIDENCE NEEDED for perceptual differentiation; NO-GO for accepting stronger or retuned production DSP.** Retain the existing implementation and artistic parameters as the reference, with the newly measured robustness limitations explicitly recorded. This is not a baseline release-safety certification.

Baseline `main`: `4eb2412682f8b3c6321ce5c8887314850ac9a697`. Local branch: `experiment/sol-ultra-live-dsp-study`. No production DSP candidate was implemented or accepted. Research code, tests, data, figures and listening artifacts are the changes. No merge, release, version bump, device routing change or live capture occurred.

## What the study establishes

The source and 224 controlled renders show three strengths of one operation. For a fixed input, Legato is the midpoint of Velvet and Melt to float32 accuracy. This is a limitation of the current profile model, not evidence of a broken mode selector or cold processing bank. All banks remain correctly warmed and numerical delayed Bypass preservation is verified, with the signed-zero representation qualification documented in the baseline analysis.

Subtlety has a material-dependent explanation. Some simple and sustained synthetic differences are largely attenuation: Melt's 12.06% raw difference on harmonic sustain becomes 1.29% after RMS matching at 48 kHz stereo. The verified CC0 passages retain about 5.48–6.71% matched difference across tested formats, so it would be wrong to explain all music as pure gain. Remaining numerical differences do not establish audible distinction, preference or fidelity.

The operator is local spectral-bin smoothing. It has no dedicated transient softener, note-connection mechanism, harmonic detector or frequency-dependent harshness control. A sharp impulse changes much less than a sustained tone; centroids can increase. LIVE must not inherit offline ALIVE's note-boundary claims merely because mode names and strengths match.

The baseline also fails two targeted robustness screens: incomplete startup WOLA weights can amplify a peak-0.5 input beyond full scale, and borrowing magnitude into near-null bins can attach substantial energy to numerically unstable phase. These findings remain visible even though existing regression tests pass. They deserve engineering investigation before wider or stronger spectral spreading.

## Phase C: hypotheses assessed against measurements

| Hypothesis | Prediction and evidence | Disposition |
|---|---|---|
| Raise the three strengths | Larger movement along the same one-dimensional direction; more attenuation and spectral spreading | Reject as a route to distinct identities; no chosen stronger preset |
| Velvet: smoothly weight spectral curvature by physical frequency | Change upper-band local structure more than low bands without changing FFT/hop. Current centroid increases show the existing kernel is not a reliable harshness reducer | Plausible future experiment, no selected cutoff/strength; must measure matched attack/band behavior and sustained-tail coloration |
| Legato: static strength-only smoothing | No explicit envelope connection or note continuity law exists | Unsupported claim. A minimal causal temporal state could be studied, but needs a defined continuity target and attack/gap/phase safeguards |
| Melt: wider local spectral-envelope smoothing | A five-bin symmetric kernel would differ structurally from the current three-bin kernel | Defer: wider spreading populates more weak bins, directly interacting with the demonstrated phase-null instability; no evidence yet of beneficial harmonic flow |
| Primed or bounded startup normalization | Remove amplification caused by missing prehistory weights while retaining warmed state and fixed delay | Directly justified robustness hypothesis; not an artistic differentiation claim. A particular fix has not been implemented or accepted |
| Continuous reconstruction near spectral nulls | Vanishing input bins should not receive finite noise-phase-dependent reconstructed energy | Directly justified robustness hypothesis; needs phase/frequency/dither sweeps and musical comparisons before choosing a correction |

A minimal Velvet research equation is `M_V = M + (s_V w(f)/4) Δ²M`, with smooth `0≤w≤1` and `f=k·sr/N`. It changes frequency weighting, but it still does not automatically soften attacks or cut high-frequency energy. No parameter is chosen from subjective preference or a larger waveform residual.

A minimal Legato direction is a bounded one-pole history on a spectral correction, rather than unimplemented note detection or more lookahead. Retaining old magnitudes while using current phases can create gap artifacts and phase ambiguity; it should be rejected if it smears rhythmic attacks, changes silence, or shifts onset/pitch behavior. A longer window would change latency/temporal behavior and is not justified by this study.

A five-bin binomial shape `[1,4,6,4,1]/16` is an example of a falsifiable Melt hypothesis, not a recommended preset. It smooths a wider local envelope; it is still not a detector of harmonically related partials.

## Why no candidate DSP was selected

The user authorized justified experiments. No additional permission is being treated as a prerequisite to prototyping. The no-candidate outcome is an engineering decision: the present evidence identifies exact structural limits and concrete robustness failures, but does not identify musical parameters that improve the intended experiences while satisfying the safeguards.

Implementing a stronger artistic candidate simply to obtain a larger numerical difference would not answer the musical question. A startup-only fix could improve a safety edge without differentiating the profiles. A null-stability fix could alter timbre enough to require its own baseline comparison. Combining these with simultaneous musical tuning would confound causes. The smallest defensible next engineering work is therefore a separate, controlled robustness experiment, followed by one artistic variable at a time if the listening target warrants it.

Phase D candidate comparison is **not applicable: zero DSP candidates were implemented**. No candidate was silently promoted, and no baseline tolerances were weakened. The unchanged baseline is preserved in the checkout and the source archive. A candidate PR is not opened because no candidate has demonstrated the required combination of benefit and safeguards. The local experimental branch and evidence are delivered for review.

## Acceptance evidence and next decision

The final Python suite is **184 passed, 1 expected failure**, including 27 study tests; the original suite alone was 157 passed, 1 expected failure. The Python wheel build passes at v3.0.0. CMake configure was attempted and cannot complete with the repository's empty JUCE/pybind11 vendor directories; Linux VST3/macOS plugin builds remain pending. This prerequisite failure is not recast as a successful build.

Worker-body distributions under two explicit CPU competitors and a short paced model remain below their hop budgets in this run. They exclude native callback/GIL scheduling, periodic device-route inspection and physical devices. Fixed retained arrays and software continuity tests do not prove long-session native reliability. See the [executed/pending gate summary](TEST_AND_REGRESSION_SUMMARY.md).

[28 integrated-loudness-matched listening samples](LISTENING_GUIDE.md) use identical passages and shared levels; raw FLOAT measurements and RMS controls are separately retained. The CC0 originals, license statements, authorship, format and hashes are documented. No current owner listening, native monitor run, ABX result, acoustic latency, or improved musical experience is claimed. The historical owner Melt preference is retained as subjective evidence, not generalized into a new preference or universal quality verdict.

For the next review, distinguish three questions: can the owner reliably hear a difference at controlled levels, which result is preferred, and do the names describe different musical behavior? These are different outcomes. Blind discrimination can inform audibility but cannot establish quality; a small unsuccessful trial does not prove indistinguishability.

Before accepting any future candidate, require whole-emitted-stream startup checks, near-null perturbation sweeps, both rates and channels, unaltered delayed Bypass, pitch/onset and stereo checks, bounded state, safe warm switching, full regressions/builds and worker distributions under realistic native load. Then obtain separately recorded native/acoustic and owner acceptance. Preserve ALIVE/interfaces/version and keep all DSP work off the callback.

**Final disposition:** the mathematical intensity-only structure is confirmed; distinct perceptual identities and a beneficial retuning remain unproven. Retain the current artistic baseline as reference, address robustness evidence in focused follow-up experiments, and do not merge or release tuning from this study.
