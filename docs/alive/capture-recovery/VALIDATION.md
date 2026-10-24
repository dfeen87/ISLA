# Validation evidence

Baseline: `6a732e03c3f0adc3f555e0ecb002e365b7e3385f`, ISLA 3.1.0.

Local macOS 26.7.2 arm64 / Python 3.13.5 / NumPy 2.5.4:

- Full acceptance command: `python -m pytest -q tests`.
- Result: **305 passed, 1 unchanged XFAIL**, existing Starlette deprecation warning,
  13.66 seconds. Service tests require localhost socket access; the restricted
  sandbox attempt had four PermissionError setup errors, then passed with socket
  access. No service test was skipped or changed.
- Intermediate run observed one pre-existing manually pumped Bypass worker timeout;
  the added halt/error assertion improves diagnosis without changing pass criteria
  or timeout. No CI timing reliability fix is claimed.
- `python tools/live_benchmark.py`: 2,400 worker-only blocks, both rates and mono /
  stereo. [Raw benchmark](worker-benchmark.json). Largest observed hop time 1.733 ms
  vs minimum 10.667 ms hop budget. No native callbacks, device validation, GIL
  competition or physical audio are included in this measurement.
- `python tools/live_reliability_probe.py --help` succeeds without opening audio.
- Focused recovery suite: **36 passed**, 6.46 seconds.
- Final implementation commit: `d215c792657cb3dcb71c031c80e8eccbf1a651b2`.
  Hosted [Python matrix](https://github.com/dfeen87/ISLA/actions/runs/40072315216)
  and [Linux/JUCE CI](https://github.com/dfeen87/ISLA/actions/runs/40072315228)
  were dispatched on that exact code. See those runs and PR #29's current checks
  for their final outcomes; subsequent evidence-only commits rerun both workflows.
- The earlier implementation `2495627faa28311f494f95b3687c6542f87b477c` passed
  all four [Python acceptance jobs](https://github.com/dfeen87/ISLA/actions/runs/40072149103).
  This does not substitute for the final implementation's CI.
- Raw local logs: [full acceptance](pytest-full.log), [recovery](pytest-recovery.log).
- Native acceptance of this fix: **pending**, with executable
  [creator checklist](NATIVE_CHECKLIST.md). Existing native records are historical.
