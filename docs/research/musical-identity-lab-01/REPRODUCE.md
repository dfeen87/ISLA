# Reproduce Experiment 01

Start with a clean clone of `dfeen87/ISLA`. Verify the v3.1.0 ref resolves to
`6a732e03c3f0adc3f555e0ecb002e365b7e3385f`; create one experimental branch from
that SHA and apply the supplied research overlay or fetch the delivered branch.
Keep main, existing tags, original study paths and production files intact.

Use Python 3.13 with the repository requirements and a separate research-only
`pyloudnorm==0.2.0`. Exact executed dependency versions are in the measurement
JSON. Optional figures use matplotlib 3.11.1. Do not install anything into the
production audio environment merely to review this package.

From the repository root, with the research dependencies available:

```sh
python -m pytest -q tests
PYTHONPATH=. python -m tools.identity_lab.run --output <new-generated-directory>
PYTHONPATH=. python -m tools.identity_lab.recording --source <Emotional_piano.wav> --output <new-recorded-directory>
PYTHONPATH=. python -m tools.identity_lab.supplement --generated <generated-directory> --recorded <recorded-directory> --output <new-supplement-directory>
PYTHONPATH=. python -m tools.identity_lab.benchmark --output <benchmark.json>
PYTHONPATH=. python -m tools.identity_lab.plots --generated <generated-directory>/measurements.json --recorded <recorded-directory>/measurements.json --supplement <supplement-directory>/supplement.json --output <new-figure-directory>
```

The complete suite uses local gRPC test sockets; restricted sandboxes may need
loopback access. No command opens an audio device. The generator and recording
commands require new output directories and refuse to overwrite them.

The included source recording is Emotional Piano by triangelx (CC0 1.0).
Required SHA-256:
`9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15`.
It is also obtainable from the primary Freesound page or the Commons mirror
linked in provenance. Do not substitute a transcoded or preview download.

Compare float32 little-endian array hashes for exact DSP reproduction on the
recorded environment. Output file SHA-256 values authenticate delivered files;
FLOAT WAV creation metadata can differ on regeneration even when arrays match.
Different FFT/library versions can change rounding; do not silently relabel
different bytes as the archived render. Timing measurements vary with host
load and are not checksum-reproducible performance guarantees.

The compact package contains reports, all listening files, numerical datasets,
source recording, code overlay and checksums. A separate raw-float archive
retains the selected 48 kHz stereo source/original/experimental renders. Full
matrix audio is deterministically regenerable; no prior evidence is overwritten.
