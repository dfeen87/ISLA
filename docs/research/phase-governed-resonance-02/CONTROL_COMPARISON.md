# Descriptive control comparison - Experiment 02

**Post-freeze descriptive analysis.** No DSP setting, threshold, acceptance limit or source was changed. These tables summarize the completed numerical ledger; they do not establish audibility, preference or novelty.

The ledger contains 1,976 records: 26 candidate/control labels across 76 source/format cells. The same musical material appears in several formats. Cells, attack windows and frames are not independent musical performances; no significance test is applied. Means below weight each source/format cell equally, including long beating and silence fixtures.

## All-cell control screen and effect size

Failed cells retain any registered engineering failure. Unresolved cells retain at least one attack flag. Waveform change is RMS residual as a percentage of input RMS; it is not an audible-effect percentage. Depth is mean active-frame control depth averaged across cells; it has different meanings across modes.

| Candidate | Failed/76 | Unresolved cells | Unresolved reference windows | Mean depth | Mean processing % | Median waveform change % | Median roughness ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| velvet_governed | 0/76 | 27 | 57 | 0.06488 | 62.733 | 0.13803 | 0.99925 |
| velvet_fixed | 0/76 | 27 | 57 | 0.13476 | 72.488 | 0.38294 | 0.99779 |
| velvet_fixed_matched | 0/76 | 27 | 57 | 0.063595 | 72.372 | 0.17222 | 0.99876 |
| velvet_attack_gated | 0/76 | 27 | 57 | 0.10264 | 64.023 | 0.26492 | 0.99874 |
| velvet_shuffled | 0/76 | 27 | 57 | 0.051347 | 61.014 | 0.11391 | 0.99949 |
| velvet_noop | 0/76 | 27 | 57 | 0 | 0 | 0 | 1 |
| velvet_production | 0/76 | 27 | 67 | n/a | n/a | 5.5633 | 0.94723 |
| velvet_exp01 | 0/76 | 27 | 66 | n/a | n/a | 5.6408 | 0.94663 |
| legato_governed | 0/76 | 26 | 56 | 0.063476 | 62.706 | 0.77313 | 0.99876 |
| legato_fixed | 0/76 | 28 | 87 | 0.25268 | 72.488 | 8.6636 | 0.91691 |
| legato_fixed_matched | 0/76 | 27 | 70 | 0.080933 | 72.372 | 2.7568 | 0.96461 |
| legato_attack_gated | 0/76 | 26 | 61 | 0.19244 | 64.023 | 2.4855 | 0.99892 |
| legato_shuffled | 0/76 | 27 | 58 | 0.042341 | 58.272 | 0.38187 | 0.99921 |
| legato_noop | 0/76 | 27 | 57 | 0 | 0 | 0 | 1 |
| legato_production | 0/76 | 26 | 75 | n/a | n/a | 8.7423 | 0.91722 |
| legato_exp01 | 0/76 | 26 | 73 | n/a | n/a | 8.7439 | 0.91737 |
| melt_governed | 0/76 | 27 | 59 | 0.093095 | 52.078 | 0.03272 | 1 |
| melt_fixed | 0/76 | 33 | 73 | 0.25268 | 72.488 | 1.4283 | 0.99984 |
| melt_fixed_matched | 0/76 | 33 | 68 | 0.086875 | 72.372 | 0.47792 | 1 |
| melt_attack_gated | 0/76 | 27 | 63 | 0.19244 | 64.023 | 0.091323 | 1 |
| melt_shuffled | 0/76 | 27 | 60 | 0.063171 | 48.986 | 0.015584 | 1 |
| melt_noop | 0/76 | 27 | 57 | 0 | 0 | 0 | 1 |
| melt_production | 18/76 | 26 | 76 | n/a | n/a | 11.921 | 0.88732 |
| melt_exp01 | 20/76 | 26 | 83 | n/a | n/a | 17.399 | 0.84053 |
| bypass | 0/76 | 27 | 57 | n/a | n/a | 0 | 1 |
| envelope_control | 12/76 | 32 | 157 | n/a | n/a | 10.704 | 0.91763 |

**No hard-screen advantage over the simpler fixed controls was demonstrated:** every governed, fixed, fixed_matched, attack_gated and shuffled path has zero failures. The remaining attack ambiguity is substantial even in exact Bypass/noop (27 cells, 57 reference windows), so a raw unresolved count cannot be attributed entirely to processing damage. Flag changes are diagnostic and do not establish physical or perceptual resolution.

All new ledger measurements compare an output with the original dry input. The archived Experiment 01 incremental screens compared each candidate with its original production mode. The new production/Exp01 failure counts do not replace or reclassify those earlier within-mode failures; their reference conditions differ.

| Governed mode | Flags shared with Bypass | Added candidate flags | Bypass flags absent on candidate |
|---|---:|---:|---:|
| velvet | 57 | 0 | 0 |
| legato | 56 | 0 | 1 |
| melt | 57 | 2 | 0 |

The fixed and fixed_matched paths have no attack-dependent history reset; universal silence resets and numerical limits remain. Attack_gated and shuffled retain the documented independent protection. Fixed_matched is based on mean target depth, so realized depth after confidence vetoes, attack protection and slew can differ. The ratios below make this mismatch explicit.

## Paired governance comparisons

Each pair uses exactly the same input cell. "Control-only failures" favors governance on registered screens; "governed-only failures" favors the control. Both counts must be read alongside processing dose. A lower roughness ratio is not inherently better musical expression.

| Mode/control | Control-only failures | Governed-only failures | Both fail | Median governed/control depth | Median governed/control waveform residual | Lower roughness: governed/control cells |
|---|---:|---:|---:|---:|---:|---:|
| velvet / velvet_fixed | 0 | 0 | 0 | 0.48281 | 0.54244 | 0 / 64 |
| velvet / velvet_fixed_matched | 0 | 0 | 0 | 0.99437 | 1.0459 | 4 / 60 |
| velvet / velvet_attack_gated | 0 | 0 | 0 | 0.56595 | 0.6305 | 0 / 60 |
| velvet / velvet_shuffled | 0 | 0 | 0 | 1.2546 | 1.2956 | 60 / 0 |
| velvet / velvet_noop | 0 | 0 | 0 | n/a | n/a | 60 / 0 |
| velvet / velvet_production | 0 | 0 | 0 | n/a | 0.030038 | 0 / 72 |
| velvet / velvet_exp01 | 0 | 0 | 0 | n/a | 0.029834 | 0 / 72 |
| velvet / envelope_control | 12 | 0 | 0 | n/a | 0.017204 | 0 / 68 |
| legato / legato_fixed | 0 | 0 | 0 | 0.24862 | 0.11906 | 0 / 68 |
| legato / legato_fixed_matched | 0 | 0 | 0 | 0.81278 | 0.39639 | 0 / 64 |
| legato / legato_attack_gated | 0 | 0 | 0 | 0.38046 | 0.45857 | 19 / 45 |
| legato / legato_shuffled | 0 | 0 | 0 | 1.3717 | 1.5763 | 39 / 21 |
| legato / legato_noop | 0 | 0 | 0 | n/a | n/a | 47 / 13 |
| legato / legato_production | 0 | 0 | 0 | n/a | 0.10792 | 0 / 72 |
| legato / legato_exp01 | 0 | 0 | 0 | n/a | 0.10796 | 0 / 72 |
| legato / envelope_control | 12 | 0 | 0 | n/a | 0.084229 | 0 / 68 |
| melt / melt_fixed | 0 | 0 | 0 | 0.3228 | 0.0652 | 19 / 49 |
| melt / melt_fixed_matched | 0 | 0 | 0 | 0.98908 | 0.07909 | 26 / 38 |
| melt / melt_attack_gated | 0 | 0 | 0 | 0.36313 | 0.37699 | 11 / 49 |
| melt / melt_shuffled | 0 | 0 | 0 | 1.6459 | 0.9594 | 19 / 41 |
| melt / melt_noop | 0 | 0 | 0 | n/a | n/a | 25 / 35 |
| melt / melt_production | 18 | 0 | 0 | n/a | 0.0044321 | 0 / 72 |
| melt / melt_exp01 | 20 | 0 | 0 | n/a | 0.0030024 | 0 / 72 |
| melt / envelope_control | 12 | 0 | 0 | n/a | 0.006853 | 0 / 68 |

## Legato continuity proxy on the connected-melody fixture

The four-format connected-melody control makes the continuity target more specific than an all-cell median. Ratios below one mean a lower envelope first-difference RMS. Governed Legato slightly increases this proxy; there is no numerical continuity-proxy improvement on this fixture, and no listening judgment is inferred.

| Candidate | Failed cells | Median roughness ratio | Median waveform change % | Mean realized depth |
|---|---:|---:|---:|---:|
| legato_governed | 0/4 | 1.00033978 | 0.71147 | 0.044335 |
| legato_fixed | 0/4 | 0.935099325 | 8.7447 | 0.29716 |
| legato_fixed_matched | 0/4 | 0.979508388 | 2.6843 | 0.086179 |
| legato_attack_gated | 0/4 | 0.99934092 | 1.154 | 0.25348 |
| legato_shuffled | 0/4 | 1.00017157 | 0.24574 | 0.035165 |
| envelope_control | 0/4 | 0.979816282 | 10.704 | n/a |

## Recorded excerpts: known and reserved

Each excerpt has four rate/channel cells. The reserved excerpt comes from the same recording and cannot establish broad musical generalization.

| Excerpt/candidate | Failed cells | Unresolved cells | Median waveform change % | Median envelope roughness ratio | Mean depth |
|---|---:|---:|---:|---:|---:|
| recorded_known / velvet_governed | 0/4 | 4 | 0.12541 | 0.99934 | 0.047577 |
| recorded_known / velvet_fixed | 0/4 | 4 | 0.40441 | 0.99772 | 0.15882 |
| recorded_known / velvet_fixed_matched | 0/4 | 4 | 0.13115 | 0.99926 | 0.050767 |
| recorded_known / velvet_attack_gated | 0/4 | 4 | 0.27041 | 0.99858 | 0.10348 |
| recorded_known / velvet_shuffled | 0/4 | 4 | 0.11292 | 0.99942 | 0.040135 |
| recorded_known / velvet_exp01 | 0/4 | 4 | 5.6221 | 0.94887 | n/a |
| recorded_known / legato_governed | 0/4 | 4 | 1.3599 | 0.99895 | 0.077014 |
| recorded_known / legato_fixed | 0/4 | 4 | 9.4549 | 0.95261 | 0.29779 |
| recorded_known / legato_fixed_matched | 0/4 | 4 | 2.9911 | 0.98414 | 0.0885 |
| recorded_known / legato_attack_gated | 0/4 | 4 | 3.2996 | 0.99762 | 0.19402 |
| recorded_known / legato_shuffled | 0/4 | 4 | 1.22 | 0.99896 | 0.064867 |
| recorded_known / legato_exp01 | 0/4 | 4 | 8.7754 | 0.92111 | n/a |
| recorded_known / melt_governed | 0/4 | 4 | 0.75977 | 1.0001 | 0.045224 |
| recorded_known / melt_fixed | 0/4 | 4 | 2.2608 | 1 | 0.29779 |
| recorded_known / melt_fixed_matched | 0/4 | 4 | 1.2221 | 1.0001 | 0.054057 |
| recorded_known / melt_attack_gated | 0/4 | 4 | 2.0672 | 0.99965 | 0.19402 |
| recorded_known / melt_shuffled | 0/4 | 4 | 0.88349 | 1 | 0.034959 |
| recorded_known / melt_exp01 | 2/4 | 4 | 16.734 | 0.85046 | n/a |
| recorded_reserved / velvet_governed | 0/4 | 4 | 0.10978 | 0.99939 | 0.045578 |
| recorded_reserved / velvet_fixed | 0/4 | 4 | 0.36857 | 0.99779 | 0.15882 |
| recorded_reserved / velvet_fixed_matched | 0/4 | 4 | 0.11533 | 0.99931 | 0.049333 |
| recorded_reserved / velvet_attack_gated | 0/4 | 4 | 0.24141 | 0.99866 | 0.10254 |
| recorded_reserved / velvet_shuffled | 0/4 | 4 | 0.094514 | 0.99949 | 0.038282 |
| recorded_reserved / velvet_exp01 | 0/4 | 4 | 5.4656 | 0.95106 | n/a |
| recorded_reserved / legato_governed | 0/4 | 4 | 1.5963 | 0.99797 | 0.080775 |
| recorded_reserved / legato_fixed | 0/4 | 4 | 9.5183 | 0.95035 | 0.29779 |
| recorded_reserved / legato_fixed_matched | 0/4 | 4 | 3.2206 | 0.98237 | 0.095072 |
| recorded_reserved / legato_attack_gated | 0/4 | 4 | 3.8025 | 0.99586 | 0.19226 |
| recorded_reserved / legato_shuffled | 0/4 | 4 | 1.4936 | 0.99783 | 0.065959 |
| recorded_reserved / legato_exp01 | 0/4 | 4 | 8.5291 | 0.92454 | n/a |
| recorded_reserved / melt_governed | 0/4 | 4 | 0.56742 | 1 | 0.038839 |
| recorded_reserved / melt_fixed | 0/4 | 4 | 2.0371 | 0.99935 | 0.29779 |
| recorded_reserved / melt_fixed_matched | 0/4 | 4 | 0.96738 | 0.99983 | 0.050892 |
| recorded_reserved / melt_attack_gated | 0/4 | 4 | 1.7304 | 0.99991 | 0.19226 |
| recorded_reserved / melt_shuffled | 0/4 | 4 | 0.55315 | 0.99999 | 0.029569 |
| recorded_reserved / melt_exp01 | 2/4 | 4 | 16.276 | 0.85757 | n/a |

## Beating, decay and stereo retention

Each carrier has eight mathematical cells: four nonzero separations, damped and undamped. Decay error is reported on the four damped cells only. These additive fixtures test specified interference; they do not model full piano-string/soundboard coupling.

| Carrier/candidate | Failed cells | Max absolute spacing error Hz | Max absolute envelope-frequency error Hz | Minimum envelope correlation | Max damped decay relative error |
|---|---:|---:|---:|---:|---:|
| beating_low / velvet_governed | 0/8 | 7.8093e-07 | 1.465e-06 | 1 | 2.3787e-05 |
| beating_low / velvet_fixed | 0/8 | 3.3892e-08 | 1.5672e-06 | 1 | 5.9598e-08 |
| beating_low / velvet_fixed_matched | 0/8 | 1.0916e-08 | 1.5673e-06 | 1 | 1.501e-08 |
| beating_low / velvet_attack_gated | 0/8 | 1.2839e-06 | 1.5515e-06 | 1 | 9.6563e-06 |
| beating_low / velvet_shuffled | 0/8 | 9.5623e-07 | 1.2914e-06 | 1 | 0.00013252 |
| beating_low / legato_governed | 0/8 | 5.2794e-05 | 9.7014e-06 | 0.99781 | 0.0016623 |
| beating_low / legato_fixed | 0/8 | 0.00085251 | 0.00023009 | 0.98216 | 0.033272 |
| beating_low / legato_fixed_matched | 0/8 | 0.00038305 | 0.00010258 | 0.99708 | 0.01238 |
| beating_low / legato_attack_gated | 0/8 | 0.00010018 | 2.7298e-05 | 0.99154 | 0.0011433 |
| beating_low / legato_shuffled | 0/8 | 0.00018497 | 8.8247e-05 | 0.99886 | 0.0057123 |
| beating_low / melt_governed | 0/8 | 1.8057e-09 | 1.5662e-06 | 1 | 7.4379e-08 |
| beating_low / melt_fixed | 0/8 | 4.9872e-09 | 1.5656e-06 | 1 | 8.9094e-08 |
| beating_low / melt_fixed_matched | 0/8 | 3.7613e-09 | 1.5657e-06 | 1 | 8.3449e-08 |
| beating_low / melt_attack_gated | 0/8 | 3.46e-09 | 1.5658e-06 | 1 | 8.1893e-08 |
| beating_low / melt_shuffled | 0/8 | 2.6073e-09 | 1.566e-06 | 1 | 7.408e-08 |
| beating_high / velvet_governed | 0/8 | 2.7061e-05 | 1.4086e-05 | 0.99978 | 0.0012717 |
| beating_high / velvet_fixed | 0/8 | 7.1481e-07 | 1.5576e-06 | 1 | 8.6834e-07 |
| beating_high / velvet_fixed_matched | 0/8 | 2.1108e-07 | 1.5625e-06 | 1 | 2.5556e-07 |
| beating_high / velvet_attack_gated | 0/8 | 3.6503e-05 | 4.9661e-06 | 0.99946 | 0.00029296 |
| beating_high / velvet_shuffled | 0/8 | 4.1897e-05 | 5.5164e-05 | 0.99988 | 0.002017 |
| beating_high / legato_governed | 0/8 | 5.2251e-05 | 1.2467e-05 | 0.99766 | 0.0017153 |
| beating_high / legato_fixed | 0/8 | 0.00085253 | 0.0002301 | 0.9822 | 0.033276 |
| beating_high / legato_fixed_matched | 0/8 | 0.00036514 | 9.7708e-05 | 0.99716 | 0.0074014 |
| beating_high / legato_attack_gated | 0/8 | 0.00010044 | 2.723e-05 | 0.99152 | 0.0011499 |
| beating_high / legato_shuffled | 0/8 | 0.00013281 | 0.00011268 | 0.99878 | 0.0037762 |
| beating_high / melt_governed | 0/8 | 1.0809e-05 | 4.5846e-06 | 1 | 0.00059932 |
| beating_high / melt_fixed | 0/8 | 2.8707e-05 | 6.0867e-06 | 0.99988 | 0.00077581 |
| beating_high / melt_fixed_matched | 0/8 | 1.8505e-05 | 5.2597e-06 | 1 | 0.0007059 |
| beating_high / melt_attack_gated | 0/8 | 2.6506e-05 | 7.9999e-06 | 1 | 0.00070985 |
| beating_high / melt_shuffled | 0/8 | 1.4845e-05 | 5.4306e-06 | 1 | 0.00056401 |

| Governed mode | Max reliable-bin stereo IPD RMS rad | Max absolute balance change dB | Max sample peak | Max 4x oversampled peak estimate |
|---|---:|---:|---:|---:|
| velvet | 0.0015897 | 0.0032102 | 0.66859 | 0.66908 |
| legato | 0.0097603 | 0.01116 | 0.66859 | 0.66919 |
| melt | 0.0089517 | 0.0010056 | 0.67324 | 0.67409 |

## What the evidence supports

- **Velvet:** governed/fixed/fixed_matched fail in 0/0/0 cells. Governed processing retains unresolved attack flags in 27 cells. Median governed/fixed_matched realized-depth ratio is 0.99437, and residual-effect ratio is 1.0459. These differences must be considered before attributing a screen difference to state governance itself.
- **Legato:** governed/fixed/fixed_matched fail in 0/0/0 cells. Governed processing retains unresolved attack flags in 26 cells. Median governed/fixed_matched realized-depth ratio is 0.81278, and residual-effect ratio is 0.39639. These differences must be considered before attributing a screen difference to state governance itself.
- **Melt:** governed/fixed/fixed_matched fail in 0/0/0 cells. Governed processing retains unresolved attack flags in 27 cells. Median governed/fixed_matched realized-depth ratio is 0.98908, and residual-effect ratio is 0.07909. These differences must be considered before attributing a screen difference to state governance itself.

**The architecture has not earned acceptance from descriptive metrics alone.** The fixed, matched, attack-gated and shuffled controls all clear the same hard screens as governance. There is therefore no binary safety-screen benefit over these controls in this run. Unequal transformation dose and incomplete perceptual evidence prevent a claim of superior musical continuity. Numerical roughness reduction is a proxy; audibility, mode distinction, piano character, expressive attacks and creator preference remain separate listening questions. All relevant gates and creator evidence are required for research PASS. Production promotion remains unauthorized.

Complete per-candidate distributions, missing-value counts, source-subset results and cell-level paired differences are in [CONTROL_COMPARISON.json](CONTROL_COMPARISON.json). Raw measurements remain in [metrics.jsonl](metrics.jsonl).

## Source integrity

| Ledger | SHA-256 |
|---|---|
| FREEZE.json | `0d41467f483776a3ed4ac260d7c38068c9a52cc2b34deacb0b63c0f7b60ecd79` |
| SOURCE_MANIFEST.json | `d1eab894f640509acfb1e6c81f6bc864433236fbb69239a273d81aced403ea68` |
| metrics.jsonl | `0351d6959b1702e300b3878baccd0c75e2ea3ae8e193ee3a612bd461a5d390b6` |
| SUMMARY.json | `ade8743f14beaacbff3b0ba67ac11a7c44e3fcc8f7d5450d67ad96e2c5efa829` |
