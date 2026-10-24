# Reproduce the LIVE DSP study

Baseline `4eb2412682f8b3c6321ce5c8887314850ac9a697` is retained in the isolated experimental checkout and supplied source archive. All study additions are research tools/tests/docs. `isla`, `phased_music_notes`, drivers, version metadata and original tests are unchanged. No candidate DSP exists in this study.

Use the included source archive, or the local experimental checkout. From the repository root, create a separate environment if needed:

```sh
python3 -m venv .venv-study
.venv-study/bin/python -m pip install -e '.[playback]' -r requirements.txt matplotlib pyloudnorm==0.2.0
```

Use that environment's Python for the following commands. `PYTHONPATH=.` makes the studied checkout authoritative. These commands never open audio devices or change routes. The acquisition command downloads only the two verified CC0 originals and refuses a checksum mismatch.

```sh
PYTHONPATH=. python tools/dsp_study.py --output study_out/study
python tools/dsp_study_acquire.py --output study_out/study/recordings
PYTHONPATH=. python tools/dsp_study.py --recordings-only \
  --recording study_out/study/recordings/Emotional_piano.wav study_out/study/recordings/Katanga.wav \
  --output study_out/study/music
PYTHONPATH=. python tools/dsp_study_safety.py --output study_out/study/safety.json
PYTHONPATH=. python tools/dsp_study_edge_cases.py --output study_out/study/baseline_edge_cases.json
PYTHONPATH=. python tools/dsp_study_benchmark.py --output study_out/study/benchmark.json
PYTHONPATH=. python tools/dsp_study_listening.py --input study_out/study
PYTHONPATH=. python tools/dsp_study_listening.py --input study_out/study/music
python tools/dsp_study_plots.py --input study_out/study --output study_out/study/plots
python tools/dsp_study_plots.py --input study_out/study/music --output study_out/study/music/plots
PYTHONPATH=. python -m pytest -q tests
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir study_out/wheels
```

The full service suite needs permission to bind localhost sockets. It does not need native audio. CMake plugin builds additionally require populated JUCE and pybind11 vendor projects, as in the repository CI setup; this study's local configure attempt failed those prerequisites and is not reported as a passing build.

The supplied raw data records Python 3.14.6, NumPy 2.5.4, SciPy 1.18.1 and SoundFile 0.14.0 on Apple Silicon macOS 26.7.2 for the main study, benchmark and regressions. Extended edge data used bundled Python 3.12.14 / NumPy 2.3.5; its JSON records that separate environment. Plotting used Matplotlib 3.11.1. Loudness comparisons used pyloudnorm 0.2.0. Metadata and source hashes are authoritative for each run. FFT/null roundoff can differ across environments; deterministic seeds do not imply cross-library bit identity.

The benchmark uses two temporary CPU competitor processes with an initialization barrier, then cleans them up. It includes worker-body metering and rings, but excludes actual callbacks, backend routing checks and devices. The short paced model is not native stress acceptance.

The code writes unaltered FLOAT measurements, separate RMS controls, and integrated-loudness listening copies. It preserves source-resampling overshoot in Bypass measurements, records all cold-start samples in edge tests, and never normalizes raw metrics to hide a failure. Original source provenance accompanies the study outputs; original WAV bytes can be reacquired with the checksum-verified downloader.

Generated audio is delivered locally and intentionally excluded from the Git research commit. The reports' `study/...` links refer to the delivered output tree or a reproduced tree with that layout. No native probe or `monitor start` command is part of reproduction.
