# ISLA LIVE DSP controlled study

October 24, 2026. The original study below preserves baseline `4eb2412682f8b3c6321ce5c8887314850ac9a697` and its unchanged v3.0.0 identity.

**Original study decision: MORE EVIDENCE NEEDED perceptually; NO-GO for accepting retuned DSP.** Profiles are mathematically three intensities of one operation. No candidate DSP was implemented in that baseline phase. Startup overshoot and near-null phase sensitivity were documented baseline limitations.

**Implementation follow-up:** [Numerical corrections and review evidence](IMPLEMENTATION_REVIEW.md) address the reproduced startup/null issues without artistic retuning. The original reports and raw measurements remain historical baseline evidence. Compare the committed [original samples](../../audio/live-baseline/PROVENANCE.md) and separate [numerical-fix samples under review](../../audio/live-robustness/PROVENANCE.md); neither implies new owner listening acceptance.

- [Baseline mathematics](LIVE_DSP_BASELINE_ANALYSIS.md)
- [224 controlled measurements and 336 pair comparisons](MODE_DIFFERENTIATION_RESULTS.md)
- [Hypotheses and recommendation](DSP_EXPERIMENT_REPORT.md)
- [Executed and pending validation](TEST_AND_REGRESSION_SUMMARY.md)
- [Listening guide](LISTENING_GUIDE.md)
- [Reproduce with the unchanged baseline](REPRODUCE.md)

Full generated audio and CC0 originals remain outside Git; the compact listening sets linked above are committed. The downloader verifies original SHA-256 before incorporation. To populate the original full study's relative audio links in a fresh clone, reproduce into this directory's `study/` layout. Baseline study tools explicitly use the frozen reference; current validation uses `tools/dsp_robustness_compare.py`. Tests do not open audio devices. No native listening or release acceptance is claimed.
