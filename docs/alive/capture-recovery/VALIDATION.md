# Validation evidence

Baseline: `6a732e03c3f0adc3f555e0ecb002e365b7e3385f`, ISLA 3.1.0.

Local macOS 26.7.2 arm64 / Python 3.13.5 / NumPy 2.5.4:

- Full acceptance command: `python -m pytest -q tests`.
- Result: **304 passed, 1 unchanged XFAIL**, existing Starlette deprecation warning,
  12.50 seconds. Service tests require localhost socket access; the restricted
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
- Final-head hosted matrix and Linux/JUCE workflow: recorded below after execution.
- Native acceptance of this fix: **pending**, with executable
  [creator checklist](NATIVE_CHECKLIST.md). Existing native records are historical.
