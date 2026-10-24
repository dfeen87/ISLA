# LIVE startup recovery admission — 2026-10-24

Status: deterministic transport repair verified locally; physical Mac/WH-CH720N
acceptance **pending**. This does not establish elimination of native overflows.
Base: current `main`, `2d424d0dd52ab036934478054a7d0858d897a268`.

## Native report and established shutdown cause

The creator reported real BlackHole 2ch -> WH-CH720N, Original/Bypass, 48 kHz:
155.5 ms ADC/DAC estimate; RMS 0.15511 / 0.11620; three input-overflow reports;
three capture discontinuities; two application output-ring misses; no application
ring failure; recoveries **0 attempted / 0 completed / 1 failed**. The fatal
reason was `Repeated capture discontinuity; recovery limit reached; stopped safely.`
This is physical evidence supplied by the creator, not a native run performed
in this repair session. It contains no callback timing trace or installed driver
versions. The exact native callback ordering cannot be proven from these totals.
The creator additionally reported a quick second of audible playback, bottom-window
statistics appearing to load and then becoming zeros, followed by Monitor: Failed.
Brief successful playback is consistent with the reproduced clean active hops
before rejection. The exact fields/timing behind the zero-stat observation are
unresolved. `_fault` and `stop` do not reset session counters or last RMS; admission
to recovery does clear instantaneous RMS until new audio arrives. Tests retain
nonzero RMS and fatal diagnostics after a later quiet-interval rejection. No UI
redraw or zero reading is treated as proof that the external source became silent.

The old admission code proves that a capture flag during the eight discarded
startup callbacks writes `_last_recovery` without incrementing attempts. A later
flag inside ten seconds of delivered frames then rejects recovery. With zero
attempts, neither an in-progress recovery nor the three-attempt lifetime limit
can explain this rejection. **The startup-derived quiet-window veto explains
the reported shutdown and counters.** The old shared error text incorrectly
implies that the lifetime budget was exhausted.

## Complete transport/display chain inspected

1. `SystemCaptureBackend.configure` resolves standalone stereo BlackHole and a
   selected stereo physical sink, validates the read-only Core Audio route and
   identities, and checks PortAudio stereo support at the requested rate.
2. `open` creates one duplex `sounddevice.Stream`, 512 frames, `latency="low"`.
   It verifies actual native stream handles and rechecks routing before start.
3. PortAudio delivers input/output status flags and ADC/DAC timestamps to
   `LiveMonitor._callback`. A capture flag counts one discontinuity even when
   both directional input flags are set. The first eight callbacks return silence
   without sending capture into DSP. Subsequent capture loss is rejected or
   admitted to the bounded recovery state machine.
4. On admission, callback output is silent. The worker validates stream/routing,
   discards old queued/in-flight audio, reseeds DSP, and acknowledges readiness.
   Completion requires delivery of fresh processed output before the existing
   eight-callback deadline. No stream restart or output fallback occurs.
5. `_fault` retains the reason and totals, sets Failed/halt, and the worker
   aborts/closes the stream. `ControlService.snapshot` carries `live.error` and
   `live.status()` into Qt's failure label and health display. No Qt layout or
   status-rendering change is necessary; an actual-callback widget test covers it.
6. `device_refresh.py` refreshes PortAudio only while owned streams are idle.
   Its active-stream guard is retained. No evidence ties discovery to this failure.

## Reproduction and narrowly bounded policy change

Fake devices use explicitly scheduled callback/worker hops and a virtual watchdog
clock; they are transport logic evidence, never physical Bluetooth acceptance.
At each supported rate, inject two startup overflow flags (callbacks 1/4 or 7/8),
then four clean active callbacks carrying nonzero audio, then another overflow.

| Sequence | Before | After |
| --- | --- | --- |
| Two startup flags, clean active audio, one later flag | 3 discontinuities; 0/0/1; Failed, closed stream | 3 discontinuities; 1/1/0; Running on the same stream after bounded reset |
| Flags on startup callbacks 7/8 and immediately on 9 | 3 discontinuities; 0/0/1; misleading limit error | Same safe stop/counters; explicitly says loss is continuing beyond startup |
| Another flag while recovery is pending | Failed | Failed; specifically says during recovery |
| Another flag inside the admitted-recovery quiet interval | Failed | Failed; specifically says within recovery quiet interval |
| Fourth lifetime attempt after three completed recoveries | Failed | Failed; specifically says session recovery budget exhausted |
| Clean startup and uninterrupted capture | Running, no recovery | Same |

Startup capture flags now update `_last_startup_gap`, **not** `_last_recovery`.
Consecutive capture loss straddling the discarded/active boundary still stops
without attempting recovery. After a clean callback separates those flags, an
active capture interruption can use the existing first recovery attempt. A clean
callback is a policy boundary, not proof of physical device-clock stability.

There is **no extension of startup grace**, no ten-second blanket flag discard,
and no retry loop. Every active capture-loss block remains silent and is never
processed as continuous music. The change only removes startup's ten-second veto
on the first otherwise-admissible active recovery. It does not change the
ten-second spacing between admitted attempts, three-attempt session budget,
eight-callback recovery deadline, eight-block rings, or eight startup callbacks.
It does not suppress flags or reset diagnostic totals when normal audio returns.

Unsafe routing/identity, disconnect, invalid timestamps, stale audio, ring faults,
output faults and repeated capture loss retain their fail-closed paths. Callback
changes are scalar state comparisons and static reason strings only: no new
array/buffer allocation, blocking operation, logging, or device enumeration.

## Underlying device-overflow cause remains unresolved

The native report confirms PortAudio input-overflow **reports**. ISLA's zero
application-ring failures do not prove native capture was healthy. Bluetooth
clock/rate adaptation, Core Audio/PortAudio buffering, scheduling/GIL pressure,
and slow worker-side routing inspection remain hypotheses, not findings from
this task. Existing historical discussion is in [ASSESSMENT.md](ASSESSMENT.md).
No reproduced implementation race or native clock fault was established here.
No latency, driver-buffer, DSP or device-discovery change is justified by this
evidence. No missing frame count or lost-audio duration can be inferred.

## Verification

Six new startup cases were first run against unmodified production code:
**6 failed** (four admitted-recovery expectations and two error classifications).
The pre-change run independently reproduced three discontinuities, 0/0/1,
nonzero RMS, zero ring failures and a safely closed stream. It did not reproduce
the exact physical latency/RMS or the creator's two application-ring misses.

After repair:

- LIVE/recovery/device-refresh/control/Qt selection: **150 passed**; the additional
  callback-to-Control-Center regression: **1 passed**.
- Full `python -m pytest -q tests`: **800 passed, 8 skipped, 1 xfailed**,
  81.28 seconds. Eight skips are native macOS codec cases; the existing XFAIL
  is legacy offline nonzero-strength chunk continuity.
- Independent production-only suite (the workflow's research/Remastered test
  exclusions): **446 passed, 8 skipped, 1 xfailed**, 35.62 seconds.
- `python -m tools.remastered_verify --output remastered-verification.json`:
  **60 cells PASS**.
- `python -m tools.remastered_live_verify --output remastered-live-verification.json`:
  **60 cells PASS**, retained-state checks included. Timing is worker-only Linux
  evidence, not a native real-time guarantee.
- `git diff --check`: passed. The production change is confined to `isla/live.py`.
  DSP/research implementations, listening gain, ALIVE, version metadata, release tags and
  PR #49 are untouched.

The first full run produced **798 passed, 1 failed, 8 skipped, 1 xfailed**:
the historical hash test correctly detected the authorized production
`isla/live.py` change. Its existing post-freeze exception pattern now verifies
LIVE's original bytes at the immutable freeze baseline and compares the current
AST outside the admission rejection block and startup-bookkeeping statements
against that baseline. Constants, backend/routing, rings, callback safety checks,
worker/DSP dispatch and stream ownership stay pinned; functional tests cover
admission and failure classification. A regression rejects changes to queue
capacity, callback timestamp protection or worker processing through this
exception. The narrowed preservation checks and strengthened startup/RMS
regressions also passed after the full run. `FREEZE.json`,
its hashes, research inputs, algorithms, outputs and scientific verdict are
unchanged. The historical experiment must still run from its pinned checkout.

Local environment: Linux x86_64, Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1,
pytest 9.1.1, sounddevice 0.5.6, PySide6 Essentials 6.12.0. Offscreen Qt and the
existing local Linux PortAudio library enable tests; no native Mac is exposed.
GitHub's macOS CI runners also do not represent the creator's physical route.

Changed files: `isla/live.py`, `tests/test_live_recovery.py`,
`tests/test_qt_window.py`, `tests/test_resonance02_slowdown_successor.py`
(post-freeze preservation test only), this report, and the historical assessment's link
to this policy update. `isla/coreaudio.py`, `isla/device_refresh.py`,
`isla/qt_window.py`, `tests/test_live.py`, and
`tools/live_reliability_probe.py` were inspected and are unchanged.

## Physical A/B acceptance — all cells pending

| Capture | Physical output | Rate | Verified native formats | Observed result |
| --- | --- | --- | --- | --- |
| BlackHole 2ch | WH-CH720N stereo | 44100 | Pending | Pending |
| BlackHole 2ch | WH-CH720N stereo | 48000 | Pending | Pending; original reported failure was at this rate |
| BlackHole 2ch | Exact listed MacBook built-in speakers | 44100 | Pending | Pending |
| BlackHole 2ch | Exact listed MacBook built-in speakers | 48000 | Pending | Pending |

On the creator's Mac, stop every other ISLA session before starting a probe.
Use the same external source, Original/Bypass, low physical volume, no other
monitor or Aggregate/Multi-Output path. Record commit, OS/Python/BlackHole/
sounddevice/PortAudio versions and Audio MIDI Setup formats before each cell.
Manually verify the intended single BlackHole capture -> physical output route;
never create a feedback path or automatically change system defaults.

For each verified output/rate pair, run separately from the checked-out repo:

```bash
python -m tools.live_reliability_probe --output "WH-CH720N" --rate 48000 --mode bypass --seconds 1800 --status-every 1 > wh-ch720n-48000.jsonl
```

Repeat with 44100 and the exact built-in output name only after verifying those
formats. Retain failures as well as successes; do not restart repeatedly to hide
one. The unchanged probe records environment, scalar state/counter changes,
routing/worker duration maxima and queue ages, and saves no audio. Its 200 ms
polling can miss intermediate callback-state transitions and cannot provide a
per-callback causal trace. Status observations are approximate cross-thread reads.
For a startup failure, capture the retained final status plus relative callback
timing/native status trace using a separately reviewed instrumented native build
if exact event ordering is needed; do not add logging/enumeration to the callback.

Record a separate listening verdict (gap, stale phrase, feedback/doubled path,
bounded latency, correct sink), startup-relative event times if available,
device identities and routing-check durations. Use the existing
[native checklist](NATIVE_CHECKLIST.md) for lifecycle/safety checks, with this
PR branch/commit rather than its historical branch. Stop and manually restore
normal macOS output afterward. No recovery flag observed means **recovery not
exercised**. A native success must identify the exact route/rate and commit;
neither deterministic tests nor historical Mac sessions establish acceptance here.
