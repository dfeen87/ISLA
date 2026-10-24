# Evidence and recovery index

This is an additive repository-integration index, prepared after the completed
experiment. It does not replace or modify any frozen file, experiment result,
checksum or original archive. The original packages remain immutable.

## Commit authority

| Purpose | Exact commit |
|---|---|
| Production baseline / verified GitHub main | `20a32de76396ab3400f14c5169276d6f03b72d08` |
| Published v3.1.1 | `3621f782d3f93334a68b7a82a3ff7ad451003ead` |
| Experiment 01 recovered source | `2be4668b9661ed931222dca09dabcb9739624b4a` |
| Experiment 02 premeasurement freeze | `07a234360e65bb5ca5dc61130d0a7116b59c008a` |
| Completed Experiment 02 implementation/report | `f775995d173689967f76f30a3826403d066c06ce` |

The integration branch retains both Experiment 02 commits unchanged. Any later
integration commit adds documentation and checksum metadata only. Experiment 01
is not resurrected as another active research branch: its exact adapter is
reused by Experiment 02, and its complete original implementation/tests/reports
remain recoverable from the self-contained preservation bundle.

## Verified external packages

Large evidence is retained outside ordinary Git. The package filenames below
identify the existing artifacts; they are **not** public download links. The
creator must supply copies to a reviewer who needs the audio/full datasets.
No unreviewed large-file hosting policy or release has been introduced.

| Artifact | Verified SHA-256 |
|---|---|
| `ISLA-Experiment-02.zip` | `497fea54ee3fd394b348824f4e70f0d2a89dfe021079b8b91e4f7747aed0524b` |
| `ISLA-Experiment-02/SHA256SUMS.json` | `f56de5f7b41a0300685edc0869d949af426a5b9681f57928c64a41bd75445a96` |
| `ISLA-Experiment-02/SOURCE_MANIFEST.json` | `d1eab894f640509acfb1e6c81f6bc864433236fbb69239a273d81aced403ea68` |
| `ISLA-Experiment-02/FREEZE.json` | `0d41467f483776a3ed4ac260d7c38068c9a52cc2b34deacb0b63c0f7b60ecd79` |
| `Experiment-01-preservation/SHA256SUMS.json` | `992c3c66fd184b0b48fb62348510148cdd9a65bdcc355d2f4aa04cdd2d26d429` |

The small committed copies are byte-identical metadata:

- [Experiment 02 checksums](evidence/EXPERIMENT02_SHA256SUMS.json): 473 package
  files, including source bundles, audio, state arrays, metric ledger, figures,
  response sheets and recovery tools.
- [Source manifest](evidence/SOURCE_MANIFEST.json): 76 source/format cells,
  including 56 checksum-matched Experiment 01 cells. It describes audio; it does
  not embed the audio samples.
- [Experiment 01 checksums](evidence/EXPERIMENT01_SHA256SUMS.json): 405 package
  files. The package's own inventory maps all 877 original logical files to
  deduplicated preserved bytes.

## Verify and restore

After obtaining and extracting the complete packages, run their existing
standalone verifiers with Python 3:

```sh
python3 /path/to/ISLA-Experiment-02/VERIFY.py
python3 /path/to/Experiment-01-preservation/VERIFY.py
```

Compare the package manifests to the committed copies above before relying on
their results. They must have the exact hashes in this index. The Experiment 01
verifier additionally checks its logical-file mapping. A small checksum list
alone cannot recover missing WAVs or a missing source archive.

Experiment 02's package includes `ISLA-Experiment-02.bundle` (complete history
and branch/HEAD refs), `ISLA-Experiment-02-source.tar.gz`, all frozen input WAVs,
`SOURCE_MANIFEST.json`, `FREEZE.json`, `RESEARCH_COMMIT.txt`, and the complete
measurement/listening evidence. Its source bundle restores the completed
implementation at `f775995`; the review branch also has the later integration
metadata. The original independent restore ran 95 core/attack/measurement tests
and matched 12 stored deterministic audio hashes.

Experiment 01's package includes
`git/ISLA-Experiment-01-full-history.bundle`, exported dangling blobs, exact
original published archives, deduplicated files, inventories, `RESTORE.py`,
`VERIFY.py` and recovery instructions. The original published branch bundle was
incremental; use the new full-history bundle as the independent restore path.
All 1,232 original Git objects and four otherwise dangling blobs were preserved.

Use [REPRODUCE.md](REPRODUCE.md) for dependency setup and exact-input replay.
Repository integration performs regression and integrity checks only; it does
not regenerate the 1,976 evaluations or replace their freeze. Fresh full replay
is needed only when an explicit verification failure or new experiment justifies
it, and must use a new output directory.

## Historical status and remaining limits

The original package's `PUBLICATION_STATUS.json` records the creator's earlier
local-only decision **at packaging time**. The subsequent explicit instruction
to push this research branch and open a research-only PR supersedes that
publication preference. The historical package is not rewritten to update this
status; the PR and integration receipt record the later publication event.

Creator responses are blank. Two slowdown timing failures, unresolved attack
ambiguities, estimator false onsets, unearned governance complexity, narrow
recording coverage and lack of LIVE/native acceptance remain visible. No
research PASS, merge, version bump or release follows from publishing this PR.

Local originals and local preservation copies are on the same machine. A second
independent device/cloud backup is recommended and has **not** been performed.
Store both complete packages in another failure domain and run both verifiers
there; matching manifests on this machine is not independent disaster recovery.
