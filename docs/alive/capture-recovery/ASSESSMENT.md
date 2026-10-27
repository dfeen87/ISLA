# LIVE capture discontinuity recovery — proposed, native acceptance pending

Historical initial policy: the startup-derived quiet-window rule below is
superseded by the [2026-10-24 startup admission investigation](STARTUP_FAILURE_2026-10-24.md).
That report distinguishes the reproduced shutdown cause from unresolved native
overflow causes and records the pending Bluetooth/built-in A/B acceptance.

## Baseline and evidence

Authoritative `main`: `6a732e03c3f0adc3f555e0ecb002e365b7e3385f`,
ISLA **3.1.0**. Dedicated branch: `fix/live-capture-discontinuity-recovery`.
`v3.0.0` remains `4eb2412682f8b3c6321ce5c8887314850ac9a697`;
`v3.1.0` remains the baseline SHA. No version, tag, release, offline ALIVE,
profile strengths, spectral equations, window, hop, or delay is changed.
Recent merged PRs inspected: #28 (routing guidance), #27 (fake-clock watchdog
seam), #26 (version alignment), #25 (LIVE numerical robustness).

The creator's actual 48 kHz BlackHole -> External Headphones Legato session
stopped with `Capture discontinuity ... overflow=True, underflow=False`,
ADC/DAC estimate 89.9 ms, application underflows 2, application overflows 0,
device status 2, and no non-finite blocks. This is native evidence of audio
loss and an unwanted shutdown, not evidence of which host workload caused it.
Earlier actual failures are retained in `../NATIVE_INITIAL_ATTEMPTS.json`;
`../NATIVE_48000.json` and `../OWNER_LISTENING_FOLLOWUP.json` establish prior
functional playback, not sustained reliability or acceptance of this fix.

**Proven code cause of shutdown:** after eight startup callbacks, either capture
flag called `_fault` unconditionally. That sets the halt event; the worker
aborts/closes the stream. A single flag suffices. `Overflows: 0` referred to
application rings, while `Device status` counted callbacks with any driver flag.
There was no distinct input-overflow total. This explains the apparent conflict.

**Reproduced in simulation:** the previous capture-status regression deliberately
expected termination on one flag. New deterministic tests inject the same flag
into all four modes and verify safe resumption, exact fresh-epoch sample sequences,
and shutdown on persistent defects. No native overflow was induced in this task.

**Separate issue:** #27's manually pumped fake-stream scheduling problem is not
this native incident. One local intermediate run hit the existing Bypass
waveform test's worker timeout. Its assertion now also wakes on halt and reports
the actual monitor error, with unchanged timeout and waveform requirements.
No timeout was raised, no test skipped, and no scheduling fix is claimed here.
The new tests explicitly schedule worker processing after manual callbacks and
force contested/in-flight interleavings separately. Hosted failures remain
separate evidence; see `VALIDATION.md`.

## Native scheduling and timing assessment

- The worker calls `CoreAudioRouting.validate` every 250 ms, synchronously.
  It enumerates all native devices and reads name, transport, alive state,
  directions, and default output. These are native property calls and can delay
  the DSP worker. They are outside the audio callback. A delayed worker can
  starve output or fill input; Python/GIL or native callback delays can also cause
  driver flags. `max_routing_ms` now measures inspection duration, including errors.
  A forced blocked-inspection test proves recovery still has a callback deadline.
  There is no native correlation trace proving inspection caused this incident.
  Validation remains synchronous and fail-closed; moving it to another thread
  without a separate liveness/freshness policy would be additional safety work.
- A duplex Python callback is not proof of identical physical device clocks.
  PortAudio's Core Audio v19.7.0 implementation uses separate AudioUnits and a
  native input ring for different devices. It sets `paInputOverflow` when that
  native ring cannot accept all input. Installed host behavior/version and unequal
  clocks must be recorded natively. ISLA cannot inspect/flush PortAudio's private
  native ring through the public callback API.
- Fixed 512 frames and `latency="low"` remain unchanged. The fixed size matches
  the DSP hop; PortAudio can add adaptation buffering for a nonzero block size.
  Neither setting nor unequal clocks has been demonstrated to cause this event.
  Changing callback sizing would require a separately tested adapter.
- Rings remain eight preallocated 512-frame float32 stereo blocks each (32,768
  sample bytes per ring, plus timestamp arrays). Full/contended input pushes and
  output pushes fail closed. Missing output is zero-filled and eight consecutive
  misses still stop. Device output underflows now have a separate consecutive
  eight-callback stop; output overflow stops immediately after startup.
- Timestamps remain PortAudio ADC/DAC estimates, not acoustic measurements.
  Non-finite or non-increasing ADC timestamps fail closed. At dequeue, source
  queue age excludes the fixed DSP delay and must lie in [0, eight hops], allowing
  1 microsecond floating-point tolerance. Stale data is muted and stopped before
  playback. No new queue capacity or delay allowance is added.

## Bounded policy and state transitions

`Running -> Recovering (audio lost) -> Running / Recovered (audio lost)`.
Any unsafe condition goes to `Failed / Stopped safely`, aborting and closing the
same stream. There is no automatic restart, rerouting, or device replacement.

1. Count every input overflow/underflow flag, including startup. Both flags in
   one callback are one capture-discontinuity event, with both directional totals.
   The flagged callback's entire input is rejected because loss may occur inside
   a fixed-size block. Its entire output is silence. Exact missing frame count is
   unknown and is never invented.
2. Admit only an isolated capture interruption: at least **10 seconds of delivered
   callback frames** since a previous admitted interruption or last startup capture
   flag; at most **three attempts per explicit session**. Startup still discards
   its existing eight callbacks; persistent loss continuing beyond startup stops.
   Ten seconds is a conservative minimum healthy interval, not an empirically
   calibrated driver rate. Three attempts bound lifetime reset/allocation work and
   expose chronic faults even when spaced apart. Explicit start resets session
   totals/budget; stop/failure retain totals for inspection.
3. Gate callbacks to silence while the worker finishes/discards any old in-flight
   result, freshly verifies active stream/device identity and routing, flushes both
   application rings, and constructs a fresh DSP instance.
   The worker acknowledges readiness only after flush and reset. Callbacks never
   flush rings, construct DSP, wait for locks, inspect devices, log, or run FFTs.
   The worker uses nonblocking flush locks too; unexpected contention stops.
4. Reset is mathematically necessary: WOLA history, wet tails, weights, and dry
   delay line refer to a continuous past that no longer exists. Reusing them would
   replay/mix old audio across the gap. A fresh instance uses the existing proven
   startup weight seeding and mode crossfade. The latest selected mode is sampled
   each worker hop. No profile is retuned and no extra recovery gain is applied.
5. Rebase timestamps to accepted post-reset capture. In-flight and queued old
   output cannot be consumed while reset is pending. Mark completed recovery only
   when the first new-epoch processed output block is delivered (it may be DSP
   prehistory silence). Its fixed DSP delay remains represented in the timestamp.
6. Completion must occur **before eight further callbacks** after the flagged
   callback: 85.33 ms at 48 kHz, 92.88 ms at 44.1 kHz. This reuses the existing
   ring/starvation horizon, independently of the unchanged 250 ms liveness check.
   Another capture fault while pending, a second within the quiet window, an
   exhausted session budget, missed deadline, buffer defect, invalid audio/timing,
   disconnect, changed identity, or invalid route stops safely. Missing callbacks
   still trigger the real monotonic watchdog.

No samples are duplicated, lost time is not filled with old music, and processing
never tries to catch up by extending a queue. Hard silence may click at the gap;
click-free concealment and uninterrupted/bit-perfect playback across loss are not
claimed. Normal uninterrupted Bypass retains its original exact numerical behavior.

## Observability

`status` distinguishes directional device flags, application ring failures,
output ring empty/contention events, all capture discontinuities, attempted /
completed / failed recoveries, fatal device errors, discarded queued/in-flight
blocks, deliberately silent recovery callbacks, and last interruption/state.
A rejected recovery counts as failed even if no reset was admitted. A fault while
recovery is pending counts once. Startup device loss is visible even though no
mid-session recovery is attempted. Non-finite muting totals remain visible.

Legacy Underflows/Overflows/Device status fields remain for compatibility; they
are not directional driver counters. Totals are cumulative within a session.
Worker/routing maxima and maximum observed source queue age aid investigation.
Status/scalar probe reads are approximate cross-thread observations, not an atomic
trace. Flags count callback reports, not the number or duration of hardware xruns.

## Regression coverage and limits

`tests/test_live_recovery.py` covers all modes and both rates with fresh-instance
sample equality after a gap, isolated/both input flags, repeated/persistent faults,
quiet and lifetime limits, forced old in-flight DSP plus both queued rings,
callback deadlines including blocked inspection, input/output flush contention,
output driver flags/starvation, unexpected frame sizes, input/DSP non-finiteness,
regressing/non-finite/stale timestamps, flagged time rebasing, rapid mode changes,
1,000 stable real-DSP blocks, retained-memory size, and repeated session cleanup.
Existing routing/native-ID, ring-contention, disconnect, watchdog, full WOLA,
Bypass, offline ALIVE/BEDROCK, identity and service tests remain in the full suite.
The 1,000-hop stream and 2,400-hop benchmark are simulated/worker evidence, not
an extended hardware listening session.

Residual risks: Python is not hard real-time; GIL/OS scheduling, USB/Bluetooth and
Core Audio/PortAudio private buffering can still fail. The application guarantees
its own old queues/history are discarded. Subsequent native callbacks and their
reported timestamps are trusted per PortAudio's contract; private host buffering
and physical DAC behavior are not observable here. Already submitted hardware
output cannot be recalled. No precise lost-audio duration or native driver fix is
claimed. The conservative limits may intentionally stop some recoverable native
sessions. A native property call that never returns cannot be cancelled by Python:
callbacks remain silent after halt, while the existing three-second stop/join
guard prevents starting another session with an owned worker still stopping.
No claim of bounded kernel-call completion is made. Sustained Mac observation, glitch listening, queue/latency evidence,
and safe physical disconnection remain release gates.

Primary references (read October 24, 2026):
[PortAudio callback contract](https://portaudio.com/docs/v19-doxydocs/portaudio_8h.html),
[sounddevice 0.5 callback flags](https://python-sounddevice.readthedocs.io/en/0.5.3/api/misc.html#sounddevice.CallbackFlags),
[PortAudio v19.7.0 Core Audio implementation](https://github.com/PortAudio/portaudio/blob/v19.7.0/src/hostapi/coreaudio/pa_mac_core.c).
The separate-device analysis is an inference from that source, not a measurement
of the creator's installed binary. See [native checklist](NATIVE_CHECKLIST.md)
and [validation evidence](VALIDATION.md).

## October 27 creator observations — physical LIVE failure and ALIVE comparison

Two creator-observed LIVE sessions used **BlackHole 2ch → Sony WH-CH720N** at
**48,000 Hz**. These are actual GUI telemetry transcripts, not synthetic
PortAudio tests, and cannot establish a complete causal trace.

1. **Original/Bypass, application input ring fault:** the first session ended
   without a Stop click, reporting `Input buffer overflow/contention; stopped
   rather than accumulating delayed audio.` Device input/output underflow and
   overflow flags were **0/0 in each direction**; application ring failures
   **1**, output empty/contention events **3**, estimated latency **485.6 ms**,
   worker/routing/queue-age maxima **8.28 / 13.47 / 32.01 ms**, and **zero**
   capture discontinuities or attempted recoveries. The original Boolean
   `BlockRing.push` does not distinguish **full** from **nonblocking lock
   contention**, so this incident cannot be retrospectively classified.
2. **Original/Bypass, native input loss:** a subsequent session reported
   `Repeated capture discontinuity within recovery quiet interval; stopped
   safely.` Device input overflows **4** (all other native directional flags
   **0**), capture discontinuities **4** including startup, attempted/completed/
   failed recoveries **1 / 1 / 1**, application ring failures **0**, estimated
   latency **155.5 ms**, and worker/routing/queue-age maxima
   **6.40 / 10.47 / 21.34 ms**. Engine telemetry: **Production requested and
   applied**, research bank **inactive**, **477 Production blocks**, **0
   Remastered blocks**, **0** observed DSP blocks exceeding the nominal
   **10.67 ms** interval, Production DSP wall-time last/peak
   **0.880 / 6.272 ms**. Thus this second failure was **reported native capture
   loss**, not demonstrated Remastered compute overload.

In contrast, traditional ALIVE file playback on the same named output reported
**14,721 callbacks, zero status events, zero underflows and zero observed DAC
clock gaps**. The loaded recording was **170.91 seconds / 44.1 kHz**, hence
**ineligible for experimental ALIVE Remastered** (its established 30-second
limit); the disabled preparation action is not proof of a click/control defect.
Traditional ALIVE file playback and continuous LIVE capture use different
transport and sample-rate contexts and are not equivalent reliability tests.

**Targeted follow-up:** preserve the current real-time fail-closed behavior and
10-second recovery quiet interval; classify the next application push failure
as `queue full` versus `lock contention`, with ring high-water, and retain
native PortAudio flags separately. The GUI may show a read-only backend-verified
Running/Stopped Safely state and distinctly colored Start/Stop controls, but
it must **not auto-restart after a fatal audio fault**. Native callback loss
may occur without the user pressing Stop. Inspect the physical setup, callback
scheduling and relevant device paths only after gathering comparable evidence.
