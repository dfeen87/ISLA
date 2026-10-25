# Three-column functional acceptance — release HOLD

Baseline: PR #69 head `f643eac259594422b9ff189e97b11a7e2fa5ee3a`,
including merged PRs #64–#68. Its three workflows / nine jobs were successful
before this pass. PR #69 was merged during verification; the follow-up branches
from `main` merge `d44561950884b436e85ec8e7354582f0a1eac593`, whose tree is identical
to the tested #69 head. This pass preserves ALIVE → v4.0 Remastered → LIVE, all labels,
styling, native pickers, the 50 ms refresh and existing processing implementations.

## Acceptance boundary

| Area | Automated result | Native creator result |
| --- | --- | --- |
| ALIVE | PASS: picker dispatch/cancel, real WAV preparation, invalid/missing input recovery, transport/position, all traditional modes, output selection and callback gain | NOT VERIFIED: Mac speakers, output switching, audible processing |
| Remastered ALIVE | PASS: admission, exclusive workspace, real spawned render/validation, all three mode requests × all 21 exact 5% depth steps, cancel/restore and previous transport preservation | NOT VERIFIED: native listening and scheduling under render load |
| LIVE | PASS: verified device filtering/selection, rates, routing rejection, real monitoring worker/DSP, engine/depth, volume/Mute, retained failure diagnostics and cleanup | NOT VERIFIED: BlackHole → Core Audio → speakers/Bluetooth |
| Ownership/transitions | PASS: incompatible controls gated, backend ownership checks, duplicate Start blocked, ALIVE → Remastered → LIVE → ALIVE and window reopen cleanup | NOT VERIFIED: physical hot-plug and native driver cleanup |
| Qt layout/interaction | PASS: held native presses, key selections, status polling, rejected operations, diagnostics scrolling and all primary controls reachable at 1040×830 / 800×600 / 1440×900 | NOT VERIFIED: macOS font metrics and native dialogs |
| Save Mix/cancellation | PASS: real float32 WAV, exact prepared PCM, no listening gain, picker cancellation, no overwrite, write/publication failures, cancel cleanup and successful retry | NOT VERIFIED: creator file-opening/listening acceptance |

PASS here describes automated operations and measured PCM. Linux offscreen Qt and
memory devices cannot establish physical audio or perceptual acceptance. Research
remains **REVISE / INCONCLUSIVE**; application release remains **HOLD**.

## Reproduced defects and minimal repairs

1. **Stale error banner after successful recovery — corrected.** Invalid file →
   valid file, and disconnected output → valid output, both left an obsolete
   “Action required” banner after the backend was healthy. `apply_state()` now
   clears it after a healthy completed operation. Busy-operation timeout messages
   and incomplete-cleanup ownership messages remain protected.
2. **Rejected LIVE engine/depth shown as selected — corrected.** Native engine
   activation auto-applies, but a rejected operation left the combo/slider showing
   values the backend had refused. The error event now invalidates their initial
   display cache so the final authoritative snapshot restores both controls.
   Unapplied depth drafts still survive ordinary polling; the rejection stays
   visible and the controls remain usable for retry.

These are the only additional production changes: **10 lines in
`isla/qt_window.py`**. No DSP math, audio callback, LIVE transport, gain adapter,
renderer, export writer, resource-ownership or CI safeguard changes.

`tests/test_control_acceptance_qt.py` adds ten interaction cases, reusing the
existing fake-device/window fixtures and predicate/event synchronization. They
exercise file-picker cancellation and real invalid-file/reload preparation,
replacing an interrupted preparation, output/rate draft persistence and stale
output rejection, rejected engine/depth rollback, failed/duplicate LIVE Start,
all 63 mode/depth preparation requests, contextual Save cancellation, all three
workspace transitions with close/reopen, and write/publication failures with
exact-PCM retry. `test_control_layout_qt.py` now checks every primary control's
reachability and parent bounds, button minimum width, Cancel visibility and
unchanged default horizontal-scroll behavior.

Before the repairs, the first seven new cases produced **3 failures / 4 passes**:
two stale-banner reproductions and one engine-rejection reproduction. An early
new test incorrectly expected Pause/resume to retain one stream; it was corrected
to assert the existing release/reopen behavior and preserved position. No existing
assertions or production safeguards were weakened.

## Historical LIVE symptoms and test synchronization

The existing real-monitor callback regression
`test_startup_capture_rejection_reaches_control_center_with_retained_counters`
still reproduces `Monitor: Failed` when capture loss continues beyond the
discarded startup interval. The exact reason and recovery/discontinuity counters
remain visible after the stream closes. Other tests retain spontaneous fault,
routing change, missing-callback watchdog, contention, starvation and DSP-failure
coverage. This supports correct fail-closed reporting; it does **not** identify
which event occurred on the creator's Mac.

Outgoing PCM verification passes 0/25/50/100% at 44.1/48 kHz for both ALIVE and
LIVE: **16 gain cells**, zero settled PCM error, unchanged capture/source, one
LIVE stream per rate. Thus the post-DSP gain path is testable and functioning;
the historical MacBook attenuation symptom still needs native reproduction.

The existing `f643eac` change to `tests/test_live.py` schedules its manually pumped
fake with a stream clock and DSP-completion gate. **200 repeated executions
passed**, retaining nonfinite silencing, a first admitted recovery, fatal repeated
capture loss and processor-failure assertions. It is test-only; separate tests
still deliberately exercise real-time watchdog and contention safeguards. No
production timing/recovery limits were changed. See the
[updated layout documentation](layout/README.md).

No independent new backend defect was confirmed in this environment, so no
speculative backend repair or separate corrective PR was created. Native brief
playback/failure, speaker attenuation and reported bubbling remain **unverified
hardware/perceptual release blockers**, not claims of resolution.

## Verification

Run with GUI/playback and `requirements.txt` installed, PortAudio discoverable,
and `QT_QPA_PLATFORM=offscreen`:

```sh
python -m pytest -q tests
python -m pytest -q tests/test_control_acceptance_qt.py tests/test_control_layout_qt.py tests/test_qt_window.py tests/test_control*.py tests/test_alive.py tests/test_live.py tests/test_mix_export*.py tests/test_remastered*.py
python -m tools.control_acceptance_verify --output gain-verification.json
python -m tools.remastered_verify --output intensity-verification.json
python -m tools.remastered_live_verify --output live-remastered-verification.json
git diff --check
```

Exact local counts and matrix summaries are recorded in
[`functional-evidence.json`](functional-evidence.json). The existing eight Linux
skips are native macOS codec tests. The existing strict expected failure concerns
nonzero-strength harmonic chunk continuity (`Residual Risk #1`), not a newly
introduced failure. A dependency deprecation warning is unrelated to these changes.
Initial container setup lacked service dependencies and discoverable PortAudio;
installing the dependencies, extracting the runtime and providing its library
lookup resolved that limitation without skipped checks or production changes.

Final-SHA hosted status is reported in the follow-up PR linked from #69. A green hosted macOS runner is
still offscreen/mocked acceptance, not creator acoustic evidence.

## Creator-only macOS acceptance checklist

Record the tested commit, macOS version, source recording, selected device,
sample rate and exact diagnostic error/counters for any failure. Start with low
hardware volume and keep it fixed for comparisons.

1. **ALIVE / speakers:** set macOS output to MacBook speakers, open a supported
   DRM-free file, and Play → Pause → Play → Stop. Filename/preparation/position
   must track the real file; Pause preserves position and Stop returns to zero.
2. **ALIVE modes / gain:** compare Original, Velvet, Legato and Melt on the same
   passage. Change ALIVE volume 25 → 0 → 25 → 50%. Silence/attenuation must be
   audible without changing selected processing. Record any bubbling and whether
   it exists in the exported WAV or only through the device.
3. **ALIVE output:** Stop, Refresh Devices, select an enumerated physical output,
   Use Listening Output, then Play. Only the applied device should sound. Retry
   after disconnecting/reconnecting it; errors must be visible and recoverable.
4. **Remastered:** load a ≤30-second mono/stereo excerpt at 44.1/48 kHz. Select a
   traditional mode, Enter Remastered, choose each research mode and 0/50/100%
   depth, and Prepare / Apply. Progress must reflect actual work; completion must
   follow validation. Changing ALIVE volume must leave processing depth unchanged.
   A full song or unsupported source rate must explain ineligibility while
   traditional ALIVE remains usable.
5. **Cancel / Return:** cancel a preparation while listening, including after
   collapsing the center settings. Cancel must remain reachable, stop the job
   and restore the remembered mode; Return after a completed render must restore
   that same traditional mode without conflicting audio ownership.
6. **Save Mix:** save a prepared traditional and Remastered mix to new WAV paths.
   Open the WAVs in another player at low volume: correct duration/rate/channels
   and selected processing, with listening attenuation excluded. Cancel the
   destination dialog, cancel an in-progress save, and try an existing path;
   no partial/corrupt destination or overwritten recording may result.
7. **LIVE / speakers:** Stop ALIVE. Set macOS Sound Output to BlackHole 2ch;
   Refresh, select BlackHole capture and MacBook speakers in ISLA, choose a
   supported rate, Apply, Recheck and Start LIVE. Play external audio. Confirm
   sustained sound, genuine changing measurements and no unexplained shutdown.
8. **LIVE processing / gain:** compare all traditional effects, then select LIVE
   Remastered with each effect and 0/50/100% depth. Its controls must remain
   independent from the center ALIVE workspace. Test 50 → 25 → 0% and Mute /
   Unmute; processed output must attenuate while capture diagnostics remain live.
9. **LIVE Bluetooth / recovery:** Stop, connect compatible Bluetooth headphones,
   Refresh, select/apply their enumerated stereo output and Start. Repeat the
   gain/Mute checks; then Stop, switch back to speakers and restart. Test an
   unavailable/disconnected output. Expect explicit errors or safe failure with
   retained reason/counters, and recovery after reselection. Do not expect success
   for a device/rate the backend rejects.
10. **Ownership / window:** ALIVE playback must block incompatible LIVE starts;
    LIVE must block ALIVE starts. Stop LIVE, close and reopen the window, and
    confirm no old sound, orphan session or duplicate stream. Stop and restore
    normal macOS output after testing. At default and smaller window sizes,
    scroll to Stop, Cancel, Save, Return and Diagnostics; no default horizontal
    scrolling or inaccessible essential controls.

If brief playback then `Monitor: Failed` recurs, retain the complete Diagnostics
text before another Start resets session totals, plus the device/rate, macOS
route, elapsed time and exact steps. Reproduce it in a separately scoped backend
investigation rather than relaxing audio safety limits here.

**No merge, tag, publication or v4.0.0 release is authorized by this report.**
