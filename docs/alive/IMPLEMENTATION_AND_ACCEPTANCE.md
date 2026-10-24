# ISLA v3.0.0 — ALIVE: implementation and acceptance

ALIVE is a release target. Package, service, and CMake versions remain 2.1.0;
no release tag is created by this change.

## Authoritative baseline

- PR #12 is merged at `88ab60d087a130fe1ad6dea3fd08b05684e0f35a`.
- PR #13 is merged at `e7b984b0bc3471b3b7d07d936f686758029d919f`.
- ALIVE branches from that current `main`, independently of the identity PR.
- `isla` forwards to the original `phased_music_notes` DSP source. The public and
  legacy aliases, HTTP/gRPC wire interfaces, JUCE/CMake configuration, and strict
  BEDROCK tests are retained. No DSP algorithm source is changed.

## Implementation

`drivers.cli:main` opens ALIVE with no arguments; the existing `--input`,
`--output`, and `--mode` file-processing route remains available. Partial offline
arguments report a usage error instead of accidentally opening the shell.

`isla.terminal` handles commands with case-insensitive verbs and modes, quoted
paths, tilde expansion, status, and cleanup for exit/EOF/Ctrl-C at the prompt.

`isla.preparation` decodes the recording and calls the existing
`drivers.api.IslaBuffer.process_buffer` once for each mode. A spawned process
keeps DSP off the command and audio threads, reports progress through a pipe,
and writes four float32 NumPy buffers to an owned temporary directory. Read-only
memory maps expose the ready buffers to playback without copying them through
the pipe. Invalid shapes/non-finite output are rejected. Replacement or exit
terminates/joins the preparation process and removes its temporary files.
The original is the float32-decoded recording, without DSP or normalization.

`isla.playback` owns one sounddevice/PortAudio OutputStream. On macOS it uses
Core Audio's default output, with the file's sample rate and channel count.
The 512-frame callback only copies prepared samples and performs a bounded 5 ms
crossfade for mode changes with preallocated weights and scratch space. It does
no file I/O, FFTs, note analysis, or smoothing. Mode selection is a published
buffer reference; changes take effect at a callback block boundary. The cursor
continues across selections. Completion drains the final block before reporting
completed. Commands close the stream before resetting/repositioning the cursor.
Pause estimates the audible sample position from the DAC clock, excluding queued
samples as far as the backend timing permits. Stream cleanup is done on the
command thread. Unexpected stream inactivity and output status flags are shown
in `status`. Completed streams are reaped on the next command or exit.

## Verification

Verified on native Apple Silicon macOS with Python 3.14.6:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[playback]'
python -m pip install -r requirements.txt
python -m pytest -q tests
```

Local result: **103 passed, 1 expected failure**. The expected failure is the existing
BEDROCK non-zero-strength chunk-streaming limitation. The unmodified service test
stack reports one FastAPI/Starlette deprecation warning. A second fresh virtual
environment with only `python -m pip install -e '.[playback]'` was also checked through both installed terminal entry points.

The editable install resolves the package's core dependencies and the playback
extra. Test/service dependencies stay in `requirements.txt`. The new ALIVE CI
matrix exercises Python 3.10/3.13 on macOS and Linux, independently of the
existing Linux JUCE build workflow. CI uses a deterministic output stand-in;
it does not assert that a hosted runner has audio hardware.

Automated acceptance covers shell launch and argument routing, a real WAV
roundtrip, missing/invalid/empty/multichannel/non-finite recordings, all prepared
modes matching the existing DSP, mono/stereo shape and rate preservation, exact
original-buffer selection, callback completion/replay, DAC-clock pause/resume,
stop/reset, crossfades, repeated commands and stream closure, output failure,
EOF/Ctrl-C cleanup, preparation cancellation, and preserved BEDROCK/identity/service
regressions. See `tests/test_alive.py`.

Native Core Audio acceptance used the Mac's selected **AirPods Pro #2 - Find My**
output. Actual OutputStreams played a quiet generated mono recording (0.30 s)
and stereo recording (5.00 s) at 44.1 kHz. The stereo run switched through
Velvet, Legato, Melt, and bypass during playback; checked continued position,
pause/resume, stop/reset/restart, full completion, and cleanup. No output status
warnings were reported. These are hardware transport/state checks, not a claim
that perceived musical quality has been accepted. Owner listening on real
recordings remains necessary before release.

## Owner macOS acceptance — required before release

1. Follow **After Cloning — Start ISLA on macOS** in README. For this PR before
   merge, check out its branch after cloning: `git checkout feature/isla-alive-terminal`.
   Select speakers/headphones in System Settings → Sound → Output at a comfortable
   volume. Launch `isla` and verify that the listed output is the intended device.
2. Run `load "~/Music/my piano.wav"` with a real mono or stereo WAV path containing
   note transitions. `status` should remain responsive throughout preparation.
   Repeat `status` until `Preparation: Ready`; confirm the file and duration.
3. Run `play`; confirm you hear the original recording. While playing, run
   `mode velvet`, `mode legato`, `mode melt`, then `bypass`. Listen for each mode
   on note transitions and confirm playback progresses without restarting.
   `status` must show the selected mode, original duration, and correct output.
4. Run `pause`, then `status`. Wait a few seconds and repeat `status`; position
   should remain fixed. Run `play` and confirm it resumes near the paused point.
5. Run `stop` and `status`; position must be 0.00. Run `play`; it starts at the
   beginning. Let it finish, then `status` must report `completed`. Run `play`
   again to verify replay from the beginning.
6. Repeat for a mono WAV and a stereo WAV, preferably at both 44.1 and 48 kHz.
   Use a stereo recording with distinct left/right content to check channel order.
   Compare original and bypass levels without changing the system volume.
7. Try `load /missing.wav`, a non-audio file, `mode invalid`, and an unknown
   command. The shell must report useful errors and remain usable. Paste a path
   containing spaces, use mixed-case commands, and run `help`.
8. Switch output while stopped and play again. Disconnect the device during
   playback; confirm status/error feedback and recovery after reconnecting. Device
   hot-plug recovery is manual in this MVP.
9. Repeat play/pause/stop/mode/bypass several times. Run `exit` while playing and
   confirm audio stops and the shell returns normally. Relaunch; test Ctrl-D and
   Ctrl-C at the prompt. Load a long file and immediately `exit` to check prompt
   preparation cancellation. No ALIVE child process should remain.
10. Retain CI results for the exact reviewed commit and record the listening
    outcome, device, macOS version, Python version, and recording properties.
    Do not tag/publish v3.0.0 until these checks are accepted.

## Known limits

- WAV mono/stereo is guaranteed; other libsndfile formats are opportunistic.
- Full-file preparation requires time, temporary disk space (four float32
  buffers), and DSP working memory. No streaming of arbitrarily large files.
- Progress/results appear when issuing commands (use `status`); the shell does
  not print unsolicited notifications while waiting for input.
- Stop during preparation resets playback; exit or a new load cancels preparation.
- Python callbacks are not hard real-time. Short transitions reduce clicks, but
  rapid switching, start/stop, device latency, and CPU pressure need listening tests.
  Sample-perfect gapless switching and pause positioning are not guaranteed.
- Source samples and DSP results are not loudness-normalized. Output conversion
  and hardware can clip values outside their representable range.
- The output is the default at stream open; no in-app device picker or automatic
  device reconnect. No system volume changes, system-wide interception, DAW,
  export command in the shell, or GUI. Offline CLI export is unchanged.
- The existing BEDROCK non-zero-strength chunk-streaming expected failure and
  JUCE Python callback risks remain documented in
  [RESIDUAL_RISKS](../bedrock/1.0/RESIDUAL_RISKS.md). ALIVE prepares whole files
  instead of executing those algorithms in its audio callback.
