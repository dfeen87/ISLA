# Experiment 02 · Phase-governed resonance

**Research only. Not approved for production promotion or release.**

This branch integrates the completed experiment without changing the frozen
DSP, parameters, thresholds, findings or original evidence packages. Production
v3.1.1 behavior, MIT licensing and author Don Michael Feeney Jr. are preserved.
No production module imports `tools/resonance02`.

Start with the [scientific report](RESEARCH_REPORT.md),
[control comparison](CONTROL_COMPARISON.md), and
[evidence/recovery index](EVIDENCE_INDEX.md). The
[specification](SPECIFICATION.md), [protocol](PROTOCOL.md) and
[freeze manifest](FREEZE.json) are the unchanged experimental authority.

## Existing implementation

- `tools/resonance02/core.py`: deterministic musical-state analysis; Velvet
  spectral curvature, Legato bounded magnitude history, and Melt bounded phase
  trajectories. The mechanisms are distinct and remain isolated from LIVE.
- `tools/resonance02/legacy01.py`: exact recovered Experiment 01 comparison
  adapter. Full Experiment 01 sources/history remain in verified preservation.
- `tools/resonance02/slowdown.py`: existing stereo-consistent offline prototype.
- `attacks.py`, `measure.py`, `corpus.py`, and `run.py`: original diagnostics,
  measurements, pinned sources and controlled comparisons.
- `present.py`, `report.py`, the supplemental audits, and `package.py`: the
  completed presentation, review and preservation workflow. Their post-freeze
  status is documented; they do not retune the experiment.

## Results and limits

The completed evaluation has 1,976 records across 76 source/format cells, plus
64 prepared paired listening trials. It is not rerun for repository integration.
All three governed identities clear the registered hard numerical screens on
these inputs; fixed and shuffled controls do too. Added governance complexity
has not demonstrated a clear advantage. Legato's connected-melody continuity
proxy slightly worsens. Creator listening remains pending.

At integration commit `9cef83b`, the frozen implementation's combined regression
result was **418 passed, 2 failed, 1 existing expected failure**, reproduced on
all four hosted Python jobs. Its two ordinary failing tests were:

```
tests/test_resonance02_slowdown.py::test_repeated_impulse_registered_event_count_and_timing[1.25]
tests/test_resonance02_slowdown.py::test_repeated_impulse_registered_event_count_and_timing[1.5]
```

Frozen protected slowdown's maximum development-fixture timing errors remain
14.5 ms and 29 ms against the unchanged 10 ms screen. Replaying the original
test file against `slowdown.py` still fails both assertions. Production-only
baseline results remain separate: 305 passed, 1 unchanged expected failure.

## Separately labeled engineering successor

[Post-freeze successor 01](SLOWDOWN_SUCCESSOR.md) corrects isolated-transient
placement in `slowdown_successor.py`. The development test file now binds to
this explicit successor; its fixtures, assertions and 10 ms limit are unchanged.
The original `slowdown.py`, frozen `run.py` and all Experiment 02 results remain
unchanged. Green successor development checks do not revise the original
research verdict or establish robust recorded-piano slowdown.

The successor record contains the root-cause derivation, before/after timing
and spread measurements, independent production acceptance, reproducible audit
command and remaining dense-onset/phase/stereo/listening limits. CI runs production
acceptance as a separately named step, followed by the complete unfiltered suite.
See PR #33 for hosted outcomes at the current head.

Other limits include false attack detections from natural beating, unresolved
recorded-transient peak ambiguities, post-stretch stereo phase changes, and a
recorded corpus drawn from one source. Native Bluetooth listening acceptance
remains unverified. An offline prototype does not establish LIVE readiness.

See [reproduction instructions](REPRODUCE.md) for the pinned environment and
full replay procedure. Large WAVs, datasets, states and archives are external
evidence; this PR contains code, tests, documentation and small manifests only.
