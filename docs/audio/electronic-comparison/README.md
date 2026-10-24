# Outbreaker + Ember: traditional and Remastered LIVE

Fourteen listening files compare the current production LIVE profiles with the
v4.0 governed Remastered LIVE modes. Each song provides one shared Original /
Bypass and six wet versions of the same 24-second passage, at normal speed.
These exports run the actual worker DSP classes offline; they are not recordings
of a physical Mac stream or exports of the traditional ALIVE file processor.

## Music credits and license

| Recording | Artist's original upload | Preserved source bytes | Audible passage |
|---|---|---|---|
| **Outbreaker — Hinkik** | [Newgrounds 681530](https://www.newgrounds.com/audio/listen/681530) | [Source parts and reconstruction](outbreaker/source/README.md) | 00:48–01:12 |
| **Ember — Kubbi** | [Newgrounds 974737](https://www.newgrounds.com/audio/listen/974737) | [ember.mp3](ember/source/ember.mp3) | 00:40–01:04 |

Both artist uploads link to **[Creative Commons Attribution-ShareAlike 3.0
Unported](https://creativecommons.org/licenses/by-sa/3.0/)**; checked October 24,
2026. The downloaded originals and all fourteen audio adaptations here are
distributed under that license. Retain the artist, title, source and license
links, and indicate the adaptations when redistributing. The audio license is
separate from ISLA's MIT software license. No artist endorsement is implied.

Adaptations: excerpting, shared input attenuation, traditional/Remastered
processing as labeled, common edge fades, constant listening-level attenuation,
and 24-bit PCM FLAC encoding. Original / Bypass receives the presentation edits
and listening-level adjustment, but no wet musical processing.

Source SHA-256 checksums:

- Outbreaker: `1049fbeeaf7919bec6d50219f525681aa4b75a0f8827a4ce13059623cbcde4ab`
- Ember: `85dc877c4e303c0455c50b7d5da99cd95ff57e436c61a78ddb49f3aa07d17e88`

The [machine-readable provenance](PROVENANCE.json) includes the artist/download
URLs, source format and measurements, source/output hashes, code fingerprints,
dependency versions, raw research diagnostics and saved-file measurements.
The original MP3 bytes are bundled for reproduction and never rewritten.
Outbreaker's source is split into two binary parts to fit the upload limit;
the renderer joins them in memory and verifies the complete original checksum.
Both sources already use lossy compression; FLAC preserves the exported PCM without another
lossy codec and cannot restore information absent from the supplied originals.

## Processing and comparison method

1. Verify the original MP3 hash and decode to float32 stereo at 44,100 Hz.
   Select the stated passage plus **two seconds immediately before it**. The
   passages were chosen for active musical content and contrasting energy,
   before rendering; the script never searches for a maximum processor difference.
2. Apply one constant attenuation to that entire 26-second input if needed to
   bring its sample peak to 0.4. Every engine/mode receives the identical buffer.
   MP3 decoding can produce peaks above 1.0; the source measurements distinguish
   these from processor overshoot. No clipping or limiting is applied.
3. Start a fresh processor for each mode and feed continuous **512-frame hops**.
   Traditional processing uses `isla.streaming.StreamingDSP` with its unchanged
   Velvet/Legato/Melt strengths **0.35 / 0.55 / 0.75**. Remastered processing uses
   `isla.remastered_streaming.RemasteredStreamingDSP` at **100% permitted depth**.
   Both are the current LIVE worker implementations; their settings are not an
   equal-intensity scale. Traditional LIVE's three profiles share a harmonic
   structure, while Remastered uses the separate governed research mechanisms.
4. Flush enough zero hops to recover the whole input, remove the common
   **1536-frame signal delay**, then discard the two-second warm-up context.
   Verify that each engine's time-aligned Bypass exactly equals the input and
   that the two Bypass versions match each other. Publish one shared reference.
5. Require each Remastered raw output to agree with the frozen offline governed
   renderer to a maximum absolute error of **1e-7** after its float32 cast. Require
   the frozen renderer's numerical/control/peak checks to pass. Check every raw
   wet output for finiteness, shape preservation and the 0.98 peak screens.
6. Apply identical **25 ms linear edge fades** to each cropped output. Measure
   all seven with pyloudnorm's default BS.1770 K weighting and integrated gating.
   Choose one target per song no higher than **-23 LUFS** and at least 3 LU below
   its quietest raw presentation, reducing it further for headroom if necessary.
   Match with constant stereo-linked scalar attenuation only. There is no
   compressor, dynamic normalization, extra EQ or reverb.
7. Save **44,100 Hz stereo / PCM24 FLAC**, decode every file, and verify its
   24-second duration, channel count, rate, finiteness and integrated loudness
   within **0.01 LU** of its song's target. If PCM rounding changes a gated block,
   correct only the constant gain and remeasure. Check sample and 4x polyphase
   peak probes below 0.98. The probe is not a certified true-peak measurement.
8. Require all seven decoded outputs within a song to be pairwise distinct.
   Record every pair's residual, plus raw and matched measurements separately.
   Verify that rendering leaves the input and processing source files unchanged.

No production source, DSP parameters, callback behavior, routing safeguards,
historical piano evidence, or frozen research data are edited by this tool.
These examples demonstrate numerically distinct output. They do not establish
audible superiority or new physical-device acceptance. The frozen research
verdict remains **REVISE / INCONCLUSIVE**.

## Reproduce

With the base project installed, run from the repository root:

```bash
python -m pip install pyloudnorm==0.2.0
python -m tools.electronic_showcase
```

The script reads bundled source recordings, opens no audio devices and performs
no downloads. It writes the fourteen FLACs and `PROVENANCE.json`. It adds no
production dependencies. Source-byte hashes, processing-file fingerprints and
library versions make the exact preparation auditable; different decoder or
numeric-library versions can change output bytes. Compare against the recorded
environment before interpreting a hash difference.

The older [piano baseline](../live-baseline/PROVENANCE.md) and
[numerical-robustness references](../live-robustness/PROVENANCE.md) remain separate
historical evidence. The README keeps their context in a collapsed archive.
