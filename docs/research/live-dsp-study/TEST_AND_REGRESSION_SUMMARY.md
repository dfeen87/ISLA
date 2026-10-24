# Test and regression summary

October 24, 2026 · baseline `4eb2412682f8b3c6321ce5c8887314850ac9a697`

Production DSP, existing tests/tolerances, ALIVE, public/legacy imports, routing and version 3.0.0 are unchanged. New tests validate the research harness; there is no new production algorithm to certify.

| Executed check | Result and scope |
|---|---|
| Original full Python suite | **157 passed, 1 XFAIL**, one existing FastAPI/Starlette warning |
| Final full Python suite | **184 passed, 1 XFAIL**, including **27 new study tests**; one existing warning |
| Initial sandbox attempt | 153 passed, 1 XFAIL, four gRPC setup errors from denied localhost sockets; retained separately. Full reruns with sockets permitted passed |
| Python wheel build | Passed, `isla_audio-3.0.0-py3-none-any.whl`; build check only, no install/release |
| CMake Release configure | Attempted; fails prerequisites because tracked `drivers/JUCE` and `drivers/pybind11` contain placeholders rather than vendor CMake projects |
| Controlled LIVE corpus | 176 synthetic + 48 recording mode measurements; 264 + 72 pair comparisons; both rates and mono/stereo |
| Independent whole-signal WOLA reference | Existing `1e-7` absolute / `1e-6` relative tolerances retained; all aligned wet renders pass, including hop seams |
| Bypass | Zero aligned numerical error for all controlled sources; extra ±1.25/subnormal probes preserved; negative-zero sign bits canonicalized |
| Warm states and switching | 2000 hops per rate/channel configuration; 128,000 exact bank-state comparisons; maximum crossfade error 2.92e-8; no stale-bank finding |
| Nonfinite handling | Whole contaminated hops agree exactly with sanitized-input controls; retained arrays remain finite; 96 checks/configuration |
| State size | Fixed 108,576 bytes mono / 180,256 stereo retained DSP arrays; does not establish whole-process RSS or native long-session bounds |
| Startup and null stress | **Baseline limitations found**, not passing acceptance gates: >1 output from peak-0.5 immediate starts; 10–12% output sensitivity near FFT nulls from tiny perturbations |
| Budget screening | Nine distribution cells: 3000 measured hops in each of eight throughput configurations, plus 1200 paced 48 kHz stereo hops; no observed modeled body/deadline overrun; native exclusions remain |
| Listening-file validation | 28 shared-target integrated-LUFS stereo files remeasured within 0.01 LU (observed <1e-8 LU); sample and 4× oversampled peak probes <1; no playback performed |
| Source preservation | Original CC0 bytes retained with SHA-256; common excerpt/resampling/downmix transformations recorded; production-tree diff is empty |

The one unchanged XFAIL is the legacy offline nonzero chunk-streaming limitation (`tests/test_harmonics_adversarial.py`), not a LIVE regression. The existing warning concerns Starlette/httpx test-client deprecation. Tests use synthetic/fake devices; none establish acoustic acceptance.

## Pending or deliberately not performed

| Gate | Status |
|---|---|
| Linux VST3 and macOS plugin builds | Pending populated vendor dependencies/platform builds; local configure failure retained |
| Hosted checks/review of experimental branch | Not dispatched; no candidate PR or release was created |
| Candidate DSP benefit/safeguard acceptance | Not applicable; no DSP candidate selected |
| Owner same-source, controlled-level listening | Samples prepared; no new feedback or preference claimed |
| Native macOS monitoring of this study | Not performed; no route/capture/device/volume changes |
| Acoustic/reference-loopback latency | Not measured; nominal DSP delay is not end-to-end latency |
| ≥30-minute realistic native stress / clock behavior | Pending; short modeled CPU load is insufficient |
| Explicit echo/glitch acceptance and physical disconnect/recovery | Pending; no hardware fault injection |
| Broad device/OS coverage and owner release acceptance | Pending |

Historical native owner observations are documented at their earlier commits in `docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md` and `OWNER_LISTENING_FOLLOWUP.json`. They are not rerun or inherited as acceptance of this study's findings.

Evidence: [final suite log](study/validation/pytest-final.log), [original suite log](study/validation/pytest-baseline-unsandboxed.log), [initial sandbox log](study/validation/pytest-baseline.log), [wheel log](study/validation/wheel-build.log), [CMake log](study/validation/cmake-configure.log), [safety JSON](study/safety.json), [budget JSON](study/benchmark.json), [edge JSON](study/baseline_edge_cases.json).

Decision: **NO-GO for accepting retuned DSP or declaring release readiness; MORE EVIDENCE NEEDED for perceptual differentiation.** Existing artistic settings are retained as the experimental reference with limitations recorded.
