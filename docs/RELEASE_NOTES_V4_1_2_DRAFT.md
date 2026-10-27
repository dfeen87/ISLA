# ISLA v4.1.2 — Remastered-First Listening Shortcut

**Status: DRAFT — source candidate only, not published.**

ISLA v4.1.2 is a small user-interface patch building on the published v4.1.1 release.

## What's new
- **Try Remastered First (up to 30s)** now appears beside the ALIVE listening workflow after a file is prepared. For eligible short recordings, it opens the existing ALIVE Remastered workspace directly, without requiring the listener to select Original, Velvet, Legato or Melt first. Users may press Play first, but don't have to.
- Clearer eligibility text explains that ALIVE Remastered is an **experimental short-excerpt research workflow**, not a full-song processing mode.
- Existing research entry, background preparation, validation, cancellation, and 5 ms playback handoff remain unchanged.
- Version identifiers across Python, HTTP API, CMake/JUCE, citation and regression tests are aligned at **4.1.2** for this source candidate. The latest published release remains **v4.1.1** until a separate release is deliberately published.

## Important limitations
- The research renderer still accepts only **nonempty mono/stereo, 44.1 or 48 kHz, at most 30-second** prepared recordings. The shortcut correctly stays disabled for longer songs, invalid sample rates, unprepared files and incompatible LIVE state.
- Full-song source selection with an independently prepared 30-second audition segment is **not implemented** here. See [Issue #85](https://github.com/dfeen87/ISLA/issues/85) for the proposed follow-up design.
- Native macOS LIVE capture interruptions remain under investigation; this GUI patch makes **no** driver, CPU-overload, audio-safety or scientific-benefit claims.
- Frozen Experiment 02 algorithms, research evidence, playback DSP, safety limits and published v4.1.0/v4.1.1 tags are untouched.

## Verification before release
- Real Qt regression: short recording can go from ALIVE Play directly to Remastered entry; previous mode is restored after cancel; no production-mode selection is required.
- Ineligible full-length recording and invalid-rate recording remain blocked, with standard ALIVE controls unaffected.
- Full macOS/Linux ALIVE and Qt suites and strict Linux build must pass on the final PR commit; conduct an ordinary Mac listening sanity check before publishing.

**Let the Music Flow. With More Choice.** 🎹💙
