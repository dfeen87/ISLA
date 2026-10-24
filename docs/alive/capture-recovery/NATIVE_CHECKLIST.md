# Creator Mac acceptance — not yet performed on this fix

Do not mark this checklist complete from CI or simulated results. Run only on
the intended Mac at a comfortable physical volume. No merge or release is part
of this procedure. Preserve any unrelated local work before checking out the PR.

## Prepare and identify the exact build

- [ ] Check out `fix/live-capture-discontinuity-recovery` and record `git rev-parse
  HEAD`, `git status --short`, macOS/Python versions, BlackHole driver version,
  sounddevice version and PortAudio version. Note dirty files explicitly.
- [ ] Use a project virtual environment, then install:

  ```bash
  python -m pip install -e '.[playback]' -r requirements.txt
  python -m pytest -q tests
  ```

- [ ] Record original macOS output, physical volume and exact physical device.
  Verify BlackHole 2ch and selected **External Headphones** are stereo at 48 kHz
  in Audio MIDI Setup. Do not use Aggregate/Multi-Output or another monitor.
- [ ] Manually choose BlackHole 2ch in macOS Sound > Output. ISLA never changes
  this setting. Select External Headphones separately inside ISLA. Use familiar
  externally playing music with autoplay disabled and record its identity.

## Interactive safety and observability

```text
python -m isla
setup audio
<choose BlackHole 2ch at the input prompt>
<choose External Headphones at the physical-output prompt>
bypass
monitor start 48000
status
mode velvet
status
mode legato
status
mode melt
status
bypass
status
monitor stop
status
exit
```

- [ ] Listen to each mode for at least 60 seconds in this initial check. Confirm
  intended output, no feedback/doubled path, finite/nonzero RMS for audible music,
  responsive commands, and stable ADC/DAC estimates. Record full statuses.
- [ ] Record every counter delta, startup flag and audible gap. `Clean` means no
  reported capture/device interruption this session; initial output-ring misses
  can still occur. `Recovered (audio lost)` is continued playback after a reported
  gap, not uninterrupted audio. Never interpret a nonzero flag total as clean.
- [ ] During a naturally occurring isolated capture fault, verify silence/gap,
  automatic continuation without `monitor start` or restarting external media,
  attempt/completed increment, last reason, no old phrase replay and no growing
  echo/delay. If no capture flag occurs, record **recovery not exercised**.
  Do not force unsafe routing to manufacture one.
- [ ] Repeated/persistent input faults, failed recovery, invalid route/device or
  persistent starvation must produce Failed, retained counters/reason and silence.
  Retain the first failure record; do not restart repeatedly to mask it.

## Extended logged sessions

With ISLA terminal monitoring stopped, keep the same manually configured route.
Run each command separately while external music plays. The helper prints JSONL
scalar records every 30 seconds and on observed counter/state changes, stops at
the duration limit, and never saves captured audio. These files are runtime
observations; add a separate written listening verdict.

```bash
python tools/live_reliability_probe.py --output "External Headphones" --rate 48000 --mode bypass --seconds 1800 > native-bypass.jsonl
python tools/live_reliability_probe.py --output "External Headphones" --rate 48000 --mode velvet --seconds 1800 > native-velvet.jsonl
python tools/live_reliability_probe.py --output "External Headphones" --rate 48000 --mode legato --seconds 3600 > native-legato.jsonl
python tools/live_reliability_probe.py --output "External Headphones" --rate 48000 --mode melt --seconds 1800 > native-melt.jsonl
```

- [ ] Complete all four observations: at least 30 minutes each, Legato 60 minutes.
  Record start/end, hardware identity and exact commit for every file. The probe
  exits nonzero on monitor failure. Duration completion alone is not acceptance.
- [ ] In each session spend an initial 10 minutes under ordinary load, then open
  and close a normal browser/app workload gradually, recording times/load changes
  in a separate note. Avoid deliberately exhausting RAM or destabilizing the OS.
  Return to ordinary load; verify bounded latency and unchanged queue capacity.
- [ ] Compare input/output flags, application failures, recovery counts and
  maximum routing duration around load changes. Flagged loss may be audible.
  Report burst patterns even if automatic recovery succeeds.
- [ ] Independently listen for stale phrases, clicks, loud transients, clipping,
  unexpected mode changes, progressive delay and monitor/media shutdown. Retain
  failures, not just favorable runs. No native elimination claim if the original
  symptom or recovery path was never exercised.

## Safe disconnection, restart and cleanup

- [ ] Pause external media and reduce physical volume before a controlled
  headphone/device disconnect. If reconnecting could expose loud built-in output,
  do not perform a live test; record it as deferred. Never route physical output
  to BlackHole or deliberately create feedback.
- [ ] In a safe live disconnect test, verify explicit Failed/silence, no automatic
  fallback output, closed stream and useful retained device error. Reconnect only
  after stop; reselect devices, restart explicitly (relaunch for stale enumeration).
- [ ] With media paused, manually change system default away from BlackHole;
  verify the single-path guard still stops. Restore the test route only manually.
- [ ] Repeat start/stop at least ten times, including stop during a recovery if
  naturally observed. Test rapid mode changes near an observed glitch and EOF /
  Ctrl-C cleanup. Totals survive stop; explicit new start begins new totals.
- [ ] Stop all ISLA monitoring/probes, pause external media, restore the original
  physical macOS Sound output, then verify normal external media playback.

Acceptance record: exact commit; session durations; source; device/driver/OS
versions; load timeline; before/after status files; observed capture faults and
recovery outcomes; audible verdict; worst latency/queue age; any failure/restart;
restoration confirmed. Require independent code review plus exact-head CI and
sustained successful native observations before asserting the failure is resolved.
