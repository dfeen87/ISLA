# ISLA Control Center — implementation and acceptance

Date: 2026-10-24. Base: `6179f0721a15808ca183a699860ca87aa6a32352` (latest verified main after merged PR #33). No open PRs were found at start. This feature does not change the package version, release tags, DSP, BlackHole installation, or system routing properties.

## Control mapping and ownership

| Window operation | Existing authority / boundary |
| --- | --- |
| Open WAV, preparation progress, cancel on close | `TerminalController` → `Preparation` (existing subprocess and mapped buffers) |
| Play / Pause / Stop / file modes | Same controller's `BufferPlayer`; original buffer and existing transitions |
| LIVE device dropdowns | Existing `_audio_setup_devices` verified CoreAudio/PortAudio filter |
| Apply selected capture/output | Existing controller device commands, only with audio stopped |
| Recheck / readiness | Existing read-only `CoreAudioRouting.snapshot/validate`; native identity tokens |
| Start LIVE | Fresh enumeration/identity validation → existing `LiveMonitor.start` → `SystemCaptureBackend.configure/open` and native stream validation |
| LIVE modes, health and stop | Same controller's `LiveMonitor` and LIVE DSP worker; mode selection remains available while monitoring and the UI shows the requested mode versus the last DSP-worker mode; scrollable health text preserves manual viewport position |
| Open Sound Settings | `/usr/bin/open x-apple.systempreferences:com.apple.Sound-Settings.extension`; five-second timeout and manual Apple menu fallback |
| Window close / desktop Quit | Serialized cleanup; ownership returns only after successful stop/cancel |

One window leases the controller. Its worker is the only GUI command owner, while the terminal waits inside the synchronous window call. No GUI-only audio engine or processing pipeline exists. The GUI event thread does no device enumeration, preparation, native stream work or blocking cleanup. The existing DSP subprocess/worker architecture remains intact.

A borrowed running stream is preserved on entry. Close stops streams and retains a completed file preparation for subsequent terminal use. In-progress preparation is canceled. A shell-launched window also closes its controller. A second window, foreign-thread commands, conflicting ALIVE/LIVE starts and changes during an active stream are refused. Uncommitted device/rate changes disable Start until applied. Device selections retain names, indices and native IDs; disappearing/replaced devices invalidate readiness. The native monitor still independently checks actual opened handles and ongoing routing.

`UIState` separates empty/preparing/ready/playing/paused/stopped file states; LIVE setup/source/devices/routing-required/ready/running/stopping; recoverable errors and fatal audio failures. Availability is derived from backend state plus an in-flight command gate. Widgets consume immutable snapshots. Slow native calls produce a warning after ten seconds without blocking the event loop. Shutdown waits for the serialized operation rather than handing a busy controller back to the terminal. Unexpected command-worker failure attempts cleanup; failed cleanup retains the lease and Close retries on a replacement cleanup thread only after the original command thread has died.

## Dependencies and scope

`.[gui]` adds `PySide6-Essentials>=6.8,<7` and existing `sounddevice>=0.5,<0.6`. Qt Widgets are sufficient; WebEngine, Qt multimedia and GUI DSP are unnecessary. PySide is imported only for `window`; base/CLI installations remain valid. Qt/PySide licensing and supported platforms remain subject to their own upstream terms; ISLA's MIT license and authorship are unchanged. No binary bundling, `.app` installer, Windows LIVE implementation or new release is included.

Local verification used Linux x86_64, Python 3.12.14, PySide6 Essentials/Shiboken 6.12.0, sounddevice 0.5.6, SoundFile 0.14.0, NumPy 2.5.4, SciPy 1.18.1 and pytest 9.1.1, plus the repository's service test requirements. The initial exploratory install included the full PySide6 meta-package; implementation and CI require only Essentials. A separate clean playback/test environment contained no PySide6. Linux PortAudio 19.6.0 was extracted into a temporary runtime directory because this host does not permit system package installation. No audio hardware was used.

## Automated evidence

The added tests use deterministic fake PortAudio/CoreAudio devices and real offscreen Qt Widgets. They exercise file lifecycle, disabled controls, exact original-buffer selection, mode switching, input/output filtering, routing mismatches, changed native IDs, hot-plug/index changes, duplicate/conflicting starts, active-session handoff, missing optional dependencies, preparation failures, cleanup failures and GUI responsiveness during delayed/failed workers.

The actual installed commands `python -m isla window`, `isla window` and interactive `window` are launched in subprocesses with a test-only normal-close timer. Interactive checks also reopen the window and verify return to a usable terminal. Existing tests retain actual bare `python -m isla`/`isla` entrypoint checks and a WAV offline-export round trip. No hidden production test flags or test-time audio streams are added.

Final local complete GUI environment: **477 passed, 1 existing xfailed**, including all **30 new coordination/widget tests**. Independent no-Qt environment: **465 passed, 1 Qt module skipped, 1 existing xfailed**. Both actual graphical launch forms, interactive open/close/reopen, and real preparation from the GUI command worker passed. Hosted exact-head run URLs and results are recorded in the PR. One existing FastAPI/Starlette dependency deprecation warning occurs; it is unrelated to audio/GUI behavior.

The new `Control Center Qt Acceptance` workflow runs the optional extra, targeted GUI checks and complete Python suite offscreen on Linux/macOS with Python 3.10/3.13. Existing ALIVE and strict Linux/JUCE checks continue independently without Qt. Hosted macOS offscreen execution is software/widget evidence, not physical device acceptance.

## Research freeze preservation

No file under `tools/resonance02` or `docs/research` is changed. Experiment 02's manifest, algorithms, protocol, evidence, successor and scientific verdict remain unchanged. Its freeze test previously hashed the evolving production terminal in the working tree, which necessarily changes to add `window`. That one entry now checks the historical bytes at the manifest's immutable baseline, `20a32de76396ab3400f14c5169276d6f03b72d08:isla/terminal.py`, against the original SHA-256. Every other frozen entry retains the original worktree hash check. CI fetches history explicitly. No hash, threshold, tolerance, research assertion or verdict is rewritten to hide a numerical failure.

## Required physical macOS acceptance — pending

No native Mac desktop or physical audio devices are available in this execution environment. None of the following is claimed complete:

- Install `.[gui]` on the creator's Mac and launch both shell forms; check native focus, keyboard navigation, resizing, file picker, window Close and desktop Quit.
- Launch interactive `window` while idle, during prepared-file playback and during LIVE. Confirm the same stream survives entry, no duplicate sound appears, close stops audio, and terminal commands work afterward. Reopen the window.
- Open a short mono and stereo WAV. Verify preparation, position/duration, Play/Pause/Stop and all production modes/Bypass by listening; verify a corrupt file produces a recoverable error.
- Select standalone BlackHole 2ch and each eligible wired physical stereo output. Confirm virtual, Aggregate, Multi-Output and mono devices are absent from listening choices.
- With macOS default set to physical headphones, confirm explicit mismatch/current/required/listening-output guidance and disabled Start. Open Sound Settings, manually choose BlackHole, Recheck, then start at both 44.1 and 48 kHz.
- Verify real input permissions, ongoing health/counters, mode transitions, Bypass, Start/Stop and source conflicts. Run sustained sessions using the existing recovery acceptance criteria.
- Unplug headphones, remove/reconnect BlackHole and change system output while running. Confirm safe stop, stale-identity refusal, clear diagnostics, reselect/recheck/relaunch guidance and clean closure.
- Confirm Sound Settings deep link and its manual fallback on the target macOS version. After stopping/closing, verify the restore-output reminder and manually restore normal system sound.
- Bluetooth pairing, device eligibility, sustained audio, latency, reconnect and profile behavior require separate real-device acceptance. No physical Bluetooth claim follows from fake-device or hosted tests.

A native call stuck permanently in an OS driver cannot be safely killed from Python. The UI stays responsive and retains ownership; normal closure waits or retries cleanup. Process termination may be necessary in that case. A hard process kill can leave existing preparation temporary files, as with the terminal. There is no automatic default-device restoration.

## Step 4 usability follow-up — LIVE modes and diagnostics

- Modes are mutually exclusive buttons, not independent toggles. Clicking Velvet, Legato, Melt or Bypass while LIVE is running changes the requested `LiveMonitor.mode` without restarting the stream. The existing monitor worker samples the mode on each input hop and applies it through the unchanged `StreamingDSP`. The interface separately displays the selected mode and the mode currently observed on the DSP worker, so users can tell whether an audio block has passed since the change.
- The LIVE diagnostics panel has a visible vertical scrollbar and a larger readable viewport. Repeated status updates preserve the reader's position; when scrolled to the bottom it continues to follow new measurements, while scrolling up does not snap back to the top or bottom.
- Automated checks must switch all four modes during a single running fake transport, observe the worker's DSP mode, verify only one stream, test both top/bottom scroll preservation, and exercise LIVE stop/cleanup. These are software correctness checks, **not native macOS listening acceptance**.
- Native owner review: while playing real system audio through BlackHole, click each mode and compare to Bypass at similar loudness. Processing may sound subtle; numerical mode selection does not establish audible preference. Scroll the diagnostics pane during active monitoring and inspect recovery, overflow and latency counters without the view jumping. Use both trackpad and scrollbar where possible.
- No change to the frozen research manifest, `isla/live.py`, `isla/streaming.py`, audio callback, safety thresholds or production DSP.
