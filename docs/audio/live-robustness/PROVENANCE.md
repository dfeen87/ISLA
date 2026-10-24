# Numerical-robustness fix listening comparison

These four files represent the **numerical fix under review**, compared with original baseline [`4eb2412682f8`](https://github.com/dfeen87/ISLA/commit/4eb2412682f8b3c6321ce5c8887314850ac9a697). The fix adds virtual silent WOLA prehistory and bounds spectral correction by float32 uncertainty. Velvet, Legato and Melt retain strengths **0.35 / 0.55 / 0.75**. No artistic retuning, audible improvement, owner preference or native acceptance is claimed. Processing identity is pinned by source hashes, rather than an uncommitted Git SHA.

Source: **Emotional Piano** by **triangelx**, May 23, 2013, published under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The [Commons page](https://commons.wikimedia.org/wiki/File:Emotional_piano.wav) attributes the [Freesound original](https://freesound.org/people/triangelx/sounds/189175/), which also states CC0. [Pinned Commons revision](https://commons.wikimedia.org/w/index.php?title=File:Emotional_piano.wav&oldid=1228875634) · [Original WAV](https://upload.wikimedia.org/wikipedia/commons/7/70/Emotional_piano.wav). Instrument and recording methods are unverified; physical acoustic piano is not assumed.

The original is **16 seconds, 44,100 Hz, stereo WAV / signed PCM16**. Its SHA-256 is:

`9661f81d37c59f230b324b830ab68c0482336af3ec117c92e73108ffb4095f15`

## Render and listening edits

The implementation comparison used the same original seconds 0–12, SciPy `resample_poly` conversion to 48 kHz (default Kaiser 5.0), and 6000 zero frames per end as the original study. Each mode was rendered from equivalent numerical-fix state and the shared 1536-frame DSP delay removed. The complete Bypass waveform equals the pinned original-baseline Bypass. This script reuses existing raw float WAVs and never runs DSP or opens audio hardware.

All four samples select **original seconds 2–8**, corresponding to raw-file frames **102000:390000**. Common **5 ms raised-cosine edge fades** and **0.125 seconds of silence at each end** are presentation edits. They do not constitute changes to LIVE. The musical excerpt is 6 seconds; each delivered file lasts **6.25 seconds**.

Integrated loudness is recomputed after the crop/fades. Each mode receives one constant stereo-linked gain toward the same target, at or below −23 LUFS and 3 LU below Bypass, with extra common reduction if needed for headroom. There is no limiter or dynamic normalization. PCM24 FLAC quantization is measured separately; FLAC is lossless for its stored PCM24, rather than bit-identical to the raw float DSP render.

| File | Gain (dB) | Shared target (LUFS) | Saved LUFS | Sample peak | 4× peak probe | Bytes |
|---|---:|---:|---:|---:|---:|---:|
| [Bypass](bypass.flac) | -7.2733 | -23.0000 | -23.0000 | 0.289671 | 0.290040 | 850,456 |
| [Velvet](velvet.flac) | -6.8337 | -23.0000 | -23.0000 | 0.295804 | 0.296072 | 852,321 |
| [Legato](legato.flac) | -6.5754 | -23.0000 | -23.0000 | 0.299802 | 0.300065 | 853,429 |
| [Melt](melt.flac) | -6.3119 | -23.0000 | -23.0000 | 0.303954 | 0.304213 | 854,610 |

All outputs are **48 kHz stereo FLAC / PCM24**, 300,000 frames. Maximum remeasured target error: **1.25e-08 LU**, below 0.01 LU. Maximum measured quantization error: **5.96e-08 full scale**, bounded by one PCM24 step (1.19e-07). The 4× oversampled peak is a probe, not a certified true-peak measurement. Total audio size: **3,410,816 bytes**.

## Reproduce and verify

From a fresh repository checkout, with NumPy, SciPy, SoundFile >=0.14 and `pyloudnorm==0.2.0` installed:

```sh
python tools/dsp_study_acquire.py --output study_out/study/recordings
PYTHONPATH=. python tools/dsp_showcase.py --input study_out/study --render-missing --current <implementation/music> --output docs/audio/live-robustness
```

The baseline `--input` is the controlled-study `study/` directory. Generate the numerical-fix comparison artifacts using the implementation report's reproduction workflow first; then replace `<implementation/music>` with its `music/` directory, containing `audio/raw/` and with `before_after.json` in its parent directory. `--render-missing` reconstructs old baseline references only, not the numerical-fix renders. The report's audio-file hashes, source transformations and exact `isla/streaming.py` / `isla/spectral.py` SHA-256 values are verified before encoding. The showcase command does not download, monitor or capture.

The separate acquisition command downloads only the reviewed CC0 originals. `--render-missing` explicitly reconstructs only absent Emotional Piano baseline raw WAVs, using frozen `tools/dsp_study_baseline.py`, equivalent fresh state and the original delay/flush convention. It copies missing historical measurement/provenance JSON from the checked-in study archive; it does not run the full 224-render study or use the current production DSP. Existing files are verified and never overwritten. Omit this flag to require an already populated input tree.

Exact WAV reconstruction also restores the archived PEAK-chunk timestamp metadata (1792819058; Melt1792819059). SoundFile otherwise inserts the current creation time, changing a whole-file checksum despite identical samples. Only that historical header field is normalized; complete pinned SHA-256 checks verify every header/sample byte before a missing WAV is written. This is archival byte reconstruction, not a claim that a new run happened at the historical timestamp. Cross-library differences are rejected rather than mislabeled as the original reference.

The [machine-readable provenance](PROVENANCE.json) records all source/raw/output SHA-256 checksums, conversion metadata, gains, quantization errors, sample/oversampled peaks and dependency versions. The [controlled study](../../research/live-dsp-study/README.md) retains raw-vs-matched measurement distinctions and outstanding native/perceptual gates. Keep playback volume fixed while comparing; equal integrated LUFS does not establish equal momentary or perceived loudness.

## Compare with the original baseline

The baseline assets remain the README showcase. These eight files use the same source crop, fades, guards, format and −23 LUFS target. Compare each mode with its corresponding baseline; no listening verdict has been supplied.

| Mode | Original baseline | Numerical fix under review |
|---|---|---|
| Bypass | [Baseline](../live-baseline/bypass.flac) | [Numerical fix](bypass.flac) |
| Velvet | [Baseline](../live-baseline/velvet.flac) | [Numerical fix](velvet.flac) |
| Legato | [Baseline](../live-baseline/legato.flac) | [Numerical fix](legato.flac) |
| Melt | [Baseline](../live-baseline/melt.flac) | [Numerical fix](melt.flac) |

Exact processing-source identities from the implementation report:

| Source | SHA-256 |
|---|---|
| `isla/streaming.py` | `221a99a03a7425595a79bb8d86460e3d0c43c4a1233ca9576d8431796983413f` |
| `isla/spectral.py` | `4ec1939543a5770ee0bcecc4b52261b30c554eab6943fc94635f8c20ce214dc3` |

Implementation `before_after.json` SHA-256: `3b575a3a3bc1c2ac6ccd42bb3474cdf986bd823ea8c4f59c1f1c6bc26864bc20`.
