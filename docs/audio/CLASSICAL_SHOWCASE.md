# Classical Remastered listening showcase

The README links sixteen 24-bit stereo FLAC listening files: two works, two speeds,
and four modes (Original / Bypass, Velvet, Legato, Melt). These are new offline
renders through `isla.remastered.render_preview`, using the governed Experiment 02
equations at 100% research depth. They are separate from the historical v3.x LIVE
examples and from the frozen research corpus. No DSP implementation was changed.

## Recording credits and audio rights

### Mozart — Lacrimosa

- Composition: Wolfgang Amadeus Mozart, *Requiem in D minor*, K. 626, “Lacrimosa.”
- Piano transcription: Sigismund Thalberg, Op. 70, No. 5A.
- Performance: **Lệ Xuân**, dated December 24, 2018 on the source page.
- [Recording and attribution](https://commons.wikimedia.org/wiki/File:Mozart,_Requiem_in_D_minor,_%27Lacrimosa%27_%E2%80%93_piano_arrangement.ogg),
  [page revision 551942809](https://commons.wikimedia.org/w/index.php?oldid=551942809).
- Recording license: **[Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/)**.
  The eight Mozart audio adaptations in `mozart-remastered/` are distributed under
  that same license. Please preserve this credit, source link, license link and
  description of changes when redistributing them. No performer endorsement is implied.
- Unmodified downloaded source: [lacrimosa-piano.ogg](mozart-remastered/source/lacrimosa-piano.ogg).
  SHA-256: `64da4163217f10fce0aee705c7a48f1e21c195f7cc52730bf5bde7fadcd4e382`.
- Source: 44,100 Hz stereo Ogg Vorbis, approximately 3:14. The excerpt uses source
  seconds **12 through 30**, before speed adjustment.

### Saint-Saëns — Organ Symphony finale

- Composition: Camille Saint-Saëns, *Symphony No. 3 in C minor*, Op. 78, “Organ,”
  Maestoso finale. The work has two large movements; the finale is commonly
  indexed as the fourth track/submovement. The source calls it “II. Maestoso.”
- Arrangement: **Gary Poffenbarger**, brass and organ.
- Performance: **Stellar Brass, United States Air Force Academy Band**.
- Recording: United States Air Force, *Fireworks for Brass and Organ*, track 1, 2007.
- [Recording, credits and rights notice](https://commons.wikimedia.org/wiki/File:Symphony_No._3_in_C_Minor_-_II._Maestoso_-_Stellar_Brass_-_United_States_Air_Force_Academy_Band.mp3),
  [page revision 1044296594](https://commons.wikimedia.org/w/index.php?oldid=1044296594).
  The source identifies the composition, arrangement, performance and recording
  as **public domain in the United States**, including the Air Force official-work
  basis for the latter three. Its original source is the
  [U.S. Air Force public-domain music collection](https://www.music.af.mil/Multimedia/Music/Public-Domain-Music/).
  That official page returned HTTP 403 during preparation; the downloaded bytes
  and credited rights statement come from the linked Commons mirror.
- Unmodified downloaded source: [maestoso-brass-organ.mp3](saint-saens-remastered/source/maestoso-brass-organ.mp3).
  SHA-256: `c5f09c9ffe52762e6b556d79612ba1e07a3dacd57295e4146a09525807b755ba`.
- Source: 44,100 Hz stereo MP3, 128 kbps, approximately 7:51. The excerpt uses the
  **opening 18 seconds** of the finale. This is a brass-and-organ arrangement.
  Crediting the Air Force does not imply its endorsement of ISLA or these adaptations.

Audio rights above are separate from the repository's MIT software license.
Source recordings were already lossy compressed. The FLAC exports preserve the
prepared PCM without adding another lossy codec; 24-bit output does not restore
detail lost in the supplied recording.

## Preparation and comparison method

1. Verify the bundled source's SHA-256 and decode with SoundFile to float32 stereo
   at the original 44,100 Hz. Select the fixed 18-second passage above.
2. Prepare a second input using FFmpeg `atempo=0.6`: 60% speed with pitch preserved.
   Pad/trim only its end to exactly 1,323,000 frames (30 seconds), accounting for
   the tempo filter's output-length rounding. No reverb is added. Time stretching
   can introduce its own artifacts; the slowed Bypass contains the same stretch.
3. Apply one common input attenuation to both speeds within a work, if needed to
   keep their sample peaks at or below 0.5. Apply identical 25 ms linear boundary
   fades to each input before processing.
4. Copy each speed's input for Original / Bypass. Independently render each of
   Velvet, Legato and Melt with `RenderRequest(mode, 100)`. The 60% examples are
   rendered on the slowed input, so the models analyze its altered timing.
5. Require the renderer's numerical and peak screens to pass. Require each wet
   render to differ from its source, and confirm that rendering preserves the
   source buffer. Frozen core SHA-256:
   `91a673b9c894d4af768ae966177d0f38c3f17d8e2b9e898e82e2082e083158a0`.
6. Measure all eight raw outputs within each work using pyloudnorm's default
   BS.1770 K weighting, 400 ms blocks and integrated gating. Choose one common
   target no higher than -23 LUFS and at least 3 LU below the quietest raw output;
   lower it further if needed for headroom. Apply a separate **constant scalar
   attenuation** to each file. No dynamic normalization or limiting is used.
7. Save 24-bit PCM FLAC. Remeasure the saved PCM and, if a gating-boundary block
   changes the measured loudness, correct only the constant scalar attenuation.
   Decode every saved file and recheck duration, channels,
   sample rate, finiteness, integrated loudness within 0.01 LU of the target, and
   sample/4× oversampling peak probes below 0.98. Check that the eight file hashes
   are distinct. The 4× probe is not a certified true-peak measurement.

Original / Bypass here means the prepared input at its labeled speed, followed
by listening-copy attenuation and PCM quantization. It is not the untouched
compressed source file. All modes at one speed receive identical prepared input;
one integrated-loudness target is shared by both speed sets within that work.
The exact gains, LUFS values, hashes and raw research diagnostics are recorded in
each [Mozart](mozart-remastered/PROVENANCE.json) and
[Saint-Saëns](saint-saens-remastered/PROVENANCE.json) report.

## Reproduce

From the repository root, with FFmpeg on your path and the base project installed:

```bash
python -m pip install pyloudnorm==0.2.0
python -m tools.classical_showcase
```

The script uses the bundled sources and writes the sixteen FLACs plus both JSON
reports. It opens no audio devices and changes no production dependencies. Each
report records the code commit, script/renderer hashes, Python, NumPy, SciPy,
SoundFile, libsndfile, pyloudnorm and FFmpeg versions. Different decoder/filter
versions may change the output bytes; compare against the recorded environment.

These samples demonstrate available experimental output, not superiority,
physical Mac/LIVE acceptance, or a completed listening study. The research verdict
remains **REVISE / INCONCLUSIVE**. Start playback quietly and compare against the
matching Bypass; audible differences and musical preference may be subtle.
