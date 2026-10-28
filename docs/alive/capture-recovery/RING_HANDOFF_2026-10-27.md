# LIVE copy-lock handoff correction — October 27, 2026

## Confirmed creator report

The creator reported a stop while Melt was selected at 44,100 Hz on
BlackHole 2ch → Sony WH-CH720N. Retained telemetry identified:

- Input last push failure **lock contention**, high-water **2 of 8**.
- Output last push failure **none**, high-water **2 of 8**.
- **Zero** native input/output overflow/underflow flags, capture discontinuities
  or recovery attempts; one application ring failure.
- Peak routing/worker/queue age **8.70 / 9.51 / 23.22 ms**.

This identifies an application mutex collision, rather than a full input queue
or a reported native capture discontinuity. It does not establish a defect in
Melt's numerical processing or prove that selecting Melt caused the collision.
The interrupted output can disrupt comparisons between modes.

## Application correction

The historical `BlockRing` holds one mutex across its NumPy block copy. The
callback performs a nonblocking acquire and stops the session if the worker is
copying at that moment, even when another slot is free. A deterministic test
reproduces this below capacity.

`SingleProducerConsumerRing` gives each thread its own publication sequence:

1. The producer copies PCM and timestamp into a free fixed slot, then publishes
   its produced sequence.
2. The consumer copies a published slot, then releases it by advancing its
   consumed sequence. The producer cannot overwrite a slot still being read.
3. Recovery discards queued history only after the existing callback gate and
   in-flight result check have quiesced access.

The application chooses this ring only on standard GIL-enabled CPython. Other
runtimes retain the historical synchronized ring. The single-producer/consumer
ownership requirement is essential; this is not a general multi-writer queue
or a hard-real-time guarantee. Background copies in separate slots remain owned
until publication/release.

`ReliableLiveMonitor` inherits the exact callback, DSP worker, timestamp checks,
capture recovery, stop and native validation from `LiveMonitor`. Its startup
adapter changes only ring construction. An AST preservation test requires its
startup/cleanup/worker-arming path to match the historical method apart from the
factory name. `isla/live.py` and all DSP algorithms remain unchanged.

Genuine eight-block saturation still fails closed. No capture-loss flag,
watchdog, stale-audio guard, rate/device check or recovery budget is disabled.
No automatic stream restart is introduced.

## Evidence

- Forced concurrent producer/consumer copies prove that incomplete slots are
  not published, occupied slots are not overwritten, and a separate free slot
  remains writable during a consumer copy. A 3,000-block concurrent wrap test
  preserves timestamps, PCM, ordering and fixed storage.
- Existing fresh-DSP recovery comparisons run against the application monitor
  for all four effects at both supported rates. Repeated capture loss, native
  disconnect/identity/routing failure, slow native startup and real queue-full
  cases retain their stop behavior.
- A **150.28-second** native Sony/44.1 kHz run requested **375 effect changes**,
  alternating Production/Remastered requests every ten seconds. It completed
  with zero native directional flags, capture gaps or ring failures. Both rings
  peaked at **2 of 8**; last push failures were **none**. Final ADC/DAC estimate
  was **183.4 ms**; peak worker/routing/queue-age **14.24 / 13.01 / 23.22 ms**.
  Input was nonzero during early observations and silent later. Physical output
  remained digitally muted; this is transport evidence, not a listening verdict.
- An additional optional in-process signal-source trial received Core Audio
  `-10863` while starting a second native stream; callbacks stopped after two
  startup callbacks and the unchanged watchdog closed LIVE. No DSP block or
  ring failure occurred. This separate driver-start result is not counted as
  a successful signal or transition test and was not hidden by relaxing guards.

Scalar long-run evidence: [ring-transition-check-2026-10-27.json](ring-transition-check-2026-10-27.json).

## References

The ownership model follows the single-reader/single-writer constraint described
by [PortAudio's ring-buffer documentation](https://portaudio.com/docs/v19-doxydocs-dev/pa__ringbuffer_8h.html).
The Python runtime gate uses the documented
[`sys._is_gil_enabled()` check](https://docs.python.org/3/howto/free-threading-python.html).
The Python implementation here does not reuse PortAudio's C ring-buffer API or
claim the same native memory-ordering implementation.
