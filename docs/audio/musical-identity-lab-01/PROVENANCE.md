# Listening source and presentation provenance

All versions are labeled, 48 kHz stereo. Generated passages are original
mathematical synthesis (MIT project generator); the recorded passage is
Emotional Piano by triangelx, [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/),
verified on its [original page](https://freesound.org/people/triangelx/sounds/189175/).
No improvement or creator preference is claimed.

The generated, recording and supplement provenance JSON files specify exact
source hashes, sample rates, source transformations, experiment amounts,
raw-array hashes, per-file scalar gains, loudness targets and remeasurements,
quantization errors, sample and 4× peak probes. PROVENANCE.json maps all 80
delivered files to their hashes. The supplement adds low-depth Melt .15 only;
center Melt .30 and Legato .50 retain their failed-screen diagnostic status.

Normal files share a passage-specific gated integrated loudness target at or
below -23 LUFS and three LU below Bypass, with common headroom attenuation if
needed. Below-gate silence and near-silence retain unity gain as FLOAT WAV.
No dynamic normalization, limiting, channel-specific gain or presentation fade
is used. Generated passages last 6 s; recorded piano lasts 6.25 s after a
six-second source crop and .125 s guards. Fixed 1536-sample DSP delay is removed.
PCM24 FLAC is lossless for encoded PCM, not identical to raw float DSP output.
The 4× oversampled peak probe is not a certified true-peak result.

Regenerate with tools/identity_lab, as described in the research reproduction
guide. Full file hashes verify delivered bytes; floating WAV metadata may vary
on regeneration. Raw float arrays and their hashes remain the numerical oracle.
