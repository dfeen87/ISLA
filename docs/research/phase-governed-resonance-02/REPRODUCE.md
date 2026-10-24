# Restore, verify and reproduce

The final evidence folder is `ISLA-Experiment-02/`. Keep it alongside the
separate `Experiment-01-preservation/` folder. Neither depends on this chat's
work directory. Use the finished output copies and their manifests as authority.

## Verify before use

Run the package's standalone `VERIFY.py` with Python 3. It checks every entry in
SHA256SUMS.json. Verify the ZIP checksum in the separate checksum file if using
the downloadable ZIP. Do not edit response sheets inside an immutable archived
evidence master; copy them elsewhere for creator responses.

The primary FREEZE.json hash is
`0d41467f483776a3ed4ac260d7c38068c9a52cc2b34deacb0b63c0f7b60ecd79`.
Primary implementation/protocol commit:
`07a234360e65bb5ca5dc61130d0a7116b59c008a`.
The final research commit is separately recorded in RESEARCH_COMMIT.txt.

## Restore the code

Use the self-contained `ISLA-Experiment-02.bundle`, then enter the clone:

```sh
git clone ISLA-Experiment-02.bundle isla-research
cd isla-research
python3.13 -m venv .venv
.venv/bin/python -m pip install -r docs/research/phase-governed-resonance-02/requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
PYTHONPATH=. .venv/bin/python -m pytest -q
```

The final combined suite intentionally remains red on two frozen slowdown
transient tests. Recorded final result: 418 passed, 2 failed, 1 expected failure.
Production baseline is 305 passed, 1 unchanged expected failure. Local service
tests need local sockets; sandbox socket denial is an environment error, not an
audio failure. No physical audio device is opened by the research evaluation.

Python 3.13.5 on macOS arm64, NumPy 2.5.4, SciPy 1.18.1, SoundFile 0.14.0 and
all exact package versions are pinned. Equivalent deterministic replay was
verified in this environment; bit identity across other FFT/library/CPU stacks
is not promised. Native JUCE/pybind11 folders are placeholders in the baseline;
native configuration cannot succeed until their separate dependency setup is
completed. No native readiness is claimed.

## Replay the frozen primary matrix

Create a fresh directory, for example `../replay-02`, copy `sources/`,
`SOURCE_MANIFEST.json` and `FREEZE.json` from the verified evidence package into
it, leaving metrics, summary and output subfolders absent. From the restored repo:

```sh
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -m tools.resonance02.run evaluate --output ../replay-02
PYTHONPATH=. NUMBA_CACHE_DIR=./work/numba-cache .venv/bin/python -m tools.resonance02.run slowdown --output ../replay-02
```

The runner verifies all frozen code/protocol hashes, default parameters, every
source hash, and production code against the pinned baseline before processing.
It refuses to overwrite an existing primary ledger or slowdown folder. The
matrix has 76 cells × 26 labels = 1,976 records. The seed is 20261024. Reuse
the existing freeze; do not create a new freeze and call it the original trial.

If regenerating sources, use corpus.py with the verified original piano WAV and
the preserved Experiment 01 evidence. The preservation restore script can
materialize `generated-measurements.json` and `recorded-measurements.json` from
the exact original paths. The new package also retains those bytes as
`provenance/exp01-generated-measurements.json` and
`provenance/exp01-recorded-measurements.json`; copy them to a scratch directory
under their unprefixed names for `--old-evidence`. The 56 reused-cell audio hashes
must match before any candidate measurement proceeds.

## Historical failure and supplementary diagnostics

```sh
PYTHONPATH=. .venv/bin/python -m tools.resonance02.attacks --source ../replay-02/sources/Emotional_piano_original.wav --measurements /path/to/evidence/provenance/exp01-recorded-measurements.json --output ../attack-replay-02
PYTHONPATH=. .venv/bin/python -m tools.resonance02.slowdown_audit --output ../replay-02
PYTHONPATH=. NUMBA_CACHE_DIR=./work/numba-cache .venv/bin/python -m tools.resonance02.estimator_audit --output ../replay-02
PYTHONPATH=. MPLCONFIGDIR=./work/matplotlib .venv/bin/python -m tools.resonance02.present --output ../replay-02 --attack-investigation ../attack-replay-02/attack-investigation.json
```

Supplementary scripts and presentation code were added after the primary freeze
and identify themselves accordingly. They do not revise DSP, thresholds or the
primary ledger. Report.py assembles the written report from recorded evidence.
The original and reserved excerpts come from the same recording; neither is a
broad independently held-out acoustic-piano corpus.

## Storage and second backup

Large WAVs, NPZ arrays and the primary metric ledger are external evidence,
excluded from ordinary Git. The source bundle restores the code; the evidence
ZIP restores the numerical/audio package. Preserve both plus the separate
Experiment 01 archive, manifests and verifier. Copy them to another physical
device or an independently administered cloud location, run both verifiers
there, and record the date/location privately. A successful same-disk restore
test does not establish an independent backup. No second independent backup has
been performed by this run.

No merge, version bump, release, LIVE deployment or production promotion is part
of these restoration commands.
