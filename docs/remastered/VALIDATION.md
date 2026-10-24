# Remastered engineering verification — October 24, 2026

Base: `d182f454a106c7f1c02f92017917db48e2db21fd` (current main, v3.3.0).
Environment: Linux x86_64, Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0,
PySide6 6.12.0; Qt offscreen, deterministic fake audio transport.

## Results

| Check | Result |
|---|---|
| Final complete diagnostic run | 688 passed, 1 existing xfailed |
| Separate production-only acceptance | 416 passed, 1 existing xfailed |
| Real Qt suite plus actual research rendering | 26 passed |
| Additional float64 endpoint equivalence, mono/stereo and both rates | 12 passed |
| Intensity verification matrix | 60/60 passed |
| Frozen research and production engine/version preservation | 44/44 byte-identical to base |
| Built wheel | Success; frozen core, preview adapter and verification utility included |
| Extracted-wheel isolated import and real spawned preparation | PASS; validated (2049, 2) float32 output |
| Whitespace / patch check | `git diff --check` passed |

The matrix includes all three modes at 0/25/50/75/100%, mono/stereo,
44.1/48 kHz. Every zero-depth raw result is an exact source copy; every 100%
raw result is bit-identical to the original governed renderer in this environment.
Every cell is deterministic, veto/rate/depth/gain/phase bounded, finite,
shape-preserving and below both sample/4x peak-admission ceilings. The generated
fixture is separate from the historical corpus. All numeric cells, applied-depth
measurements, veto counts, RMS/peak levels and residuals are retained in
[INTENSITY_MATRIX.json](INTENSITY_MATRIX.json).

The tests also exercise real child processes and their cancellation, rejection
of hot audio, source admission limits, failed workers/invalid buffers, repeated
replacement, Bypass/production/Stop/reload/close cancellation, same-stream
crossfades, playing/paused position retention, signed-zero identity, independent
stereo endpoint equivalence and silent-channel/antiphase relationships.

## Execution history and limitations

An initial complete run passed 676 tests with one existing expected failure.
Twelve float64 equivalence cases were then added and passed separately. The
post-UI-change Qt suite passed all 26 tests, and production-only acceptance
passed independently.

A repeated combined run subsequently encountered a Qt test failure and native
segmentation fault while processing offscreen events, before reaching the new
math tests. [pytest-retry-aborted.log](pytest-retry-aborted.log) preserves its
traceback. No failure was marked xfail, skipped or given a looser assertion.
The diagnostic rerun used verbose test identities and completed with **688 passed,
1 existing xfailed**; the separate Qt suite also passed. This intermittent GUI fault remains a limitation
until supported-platform CI and native use establish its behavior.

Early setup attempts lacked PortAudio and installed console scripts outside the
test interpreter directory. A dedicated virtual environment and an extracted
Ubuntu PortAudio library supplied via `LD_LIBRARY_PATH` resolved those entrypoint
failures. An early intermediate-depth comparison used a different floating-point
operation order (`depth*I/100` versus `depth*(I/100)`); it differed by at most
5.6e-17 at 75%. The test now uses the contract's normalized intensity operation
order and retains exact equality. The adapter math was not changed to fit output.

One existing Starlette/httpx deprecation warning remains. No new xfail, production
engine change, scientific parameter tuning, or historical result replacement was
introduced. The research REVISE / INCONCLUSIVE verdict remains unchanged.

Native Mac audio and creator listening acceptance are **pending**. Offscreen Qt
and fake transports do not prove physical output, audible continuity, absence of
artifacts, user preference, or universal stereo transparency. See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for the native checklist and reproduction
commands. CI reports are separate from this local run.
