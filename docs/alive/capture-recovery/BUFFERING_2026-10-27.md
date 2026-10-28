# Native LIVE buffering investigation — October 27, 2026

The owner reported **Repeated capture discontinuity within recovery quiet
interval; stopped safely** immediately after Apply / Start LIVE. This was
reproduced on the owner's Mac with standalone BlackHole 2ch → Sony WH-CH720N.
The ten-second recovery guard was responding to real PortAudio input-overflow
flags. The text was not merely a stale UI warning.

## Before: native comparison

The same production engine/worker and muted post-DSP listening adapter ran at
both supported rates with low/high native buffering. No captured PCM was saved;
only scalar observations were retained. Each trial was capped at 20 seconds.

| Rate | Driver buffering | Time observed including setup | Outcome |
| --- | --- | --- | --- |
| 48 kHz | low | 1.03 s | Quiet-interval stop; 3 input-overflow flags, 1 completed recovery |
| 48 kHz | high | 4.33 s | Application input-ring failure; 0 native flags |
| 44.1 kHz | low | 1.41 s | Quiet-interval stop; 4 input-overflow flags, 1 completed recovery |
| 44.1 kHz | high | 20.31 s | Completed; 1,688 callbacks, no native flags or ring failures |

The Sony output's PortAudio default rate was 44,100 Hz. BlackHole's was
48,000 Hz. These observations support selecting robust buffering and the output's
usual supported rate; they do not prove which driver/clock interaction caused
loss. The 48 kHz high-buffering ring failure was not classified by that initial
probe. No recovery threshold has been loosened to hide it.

## Application changes

- `BufferedSystemCaptureBackend` is an application adapter over the historical
  backend. It requests `latency='high'` and retains pre-start verification of both
  actual native stream IDs and routing, with close-on-validation-failure.
- The Control Center suggests a newly selected output's supported native rate.
  Explicit user choices survive focus loss, output reselection and status polls.
  A borrowed terminal selection is also initialized from verified device metadata
  when there is no existing LIVE configuration.
- Terminal `monitor start` matches the selected output's supported default rate;
  explicit 44100/48000 overrides remain available. Unsupported/unknown defaults
  fall back to 48000; actual configuration still checks device support.
- A pending GUI volume/mute change reaches the worker before Start LIVE creates
  the processor. A device/rate edit cannot start a stale configuration between
  two interface polls.
- The failure message now gives Recheck / Apply / Start instructions and removes
  doubled punctuation. The exact failure and counters remain in diagnostics.
  Retry is explicit; there is no automatic restart.

`isla/live.py`, DSP math, callback size, ring capacity, device/route validation,
startup discards, recovery deadline, ten-second quiet interval and three-attempt
budget are unchanged. No macOS audio property, permission or routing default was
written. The application requests driver buffering and conversion through the
normal stream-open interface.

## After: native checks

Using the actual patched TerminalController/backend and digitally muted physical
output, an 81.00-second session completed all four modes in Production followed
by all four in Remastered, 100% depth:

- 6,918 callbacks; zero native directional status flags, capture gaps, recovery
  attempts or ring failures.
- Two initial application output-ring misses; input/output high-water 2 of 8.
- Peak worker 7.09 ms; peak routing inspection 11.82 ms; max queue age 23.22 ms.
- Final input RMS was zero, so this establishes transport operation with silent
  input, not a music listening result.

A second 32.95-second run sent a generated nonzero test signal to BlackHole and
again exercised all four modes in both engines, with the physical output muted:

- 2,778 callbacks; zero native status flags, capture gaps, recovery attempts or
  ring failures. Per-mode input RMS was nonzero; final input RMS 0.13832.
- Two initial application output-ring misses; both rings high-water 2 of 8.
- Peak worker 9.43 ms; peak routing inspection 13.86 ms; max queue age 23.22 ms.
- Final ADC/DAC latency estimate 183.4 ms. PortAudio's reported stream latencies
  are separate estimates and should not be added to or substituted for this.

These are short, single-Mac transport checks. Physical listening quality,
long-session Bluetooth reliability and every other output/rate combination are
not established. Higher driver buffering can increase audible monitoring delay.

Raw scalar records: [before](buffering-before-2026-10-27.jsonl),
[after/silence](buffering-after-2026-10-27.jsonl),
[after/nonzero input](buffering-signal-2026-10-27.jsonl).

The buffering choice follows the library's documented tradeoff: high latency is
usually more robust against buffer under/overflows. See the
[official sounddevice stream documentation](https://python-sounddevice.readthedocs.io/en/0.5.0/_modules/sounddevice.html).

## Regression coverage

`test_buffered_capture.py` covers supported/fallback rates, explicit terminal
rate overrides, the selected application backend, verified stream arguments and
cleanup on native-ID or routing failure. `test_live_startup_defaults_qt.py`
covers output-rate suggestions, preserved explicit drafts, same-tick mute/start,
stale device/rate prevention, retained capture-failure evidence and manual retry.
The existing LIVE/recovery tests continue to exercise the unchanged fault guards.

Runtime: macOS-26.7.2-arm64-arm-64bit-Mach-O; Python 3.13.13, sounddevice 0.5.6, NumPy 2.5.4.

The installed editable package metadata was also refreshed from stale 4.0.0 to the checkout’s existing 4.1.2. Filename-search tests now inject a fixture-only finder into spawned search jobs so the owner’s real Spotlight matches and large media folders cannot contaminate tests. Production computer-wide search behavior is unchanged.
