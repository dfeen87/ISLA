# ISLA
### Phase-aligned musical note smoothing · an offline-first audio DSP project

![License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-BEDROCK--in--review-yellow)
[![CI](https://github.com/dfeen87/Phased-Music-Notes/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/Phased-Music-Notes/actions/workflows/ci.yml)

**ISLA** is the new name for **Phased-Music-Notes**: an experimental audio engineering project exploring smoother transitions between musical notes with phase-aware analysis, transient smoothing, and harmonic blending.

**Dedicated to Isla, the creator's niece.** The name celebrates the idea that music and thoughtful engineering can make expressive moments feel a little softer.

**Current scope:** Offline Python DSP and regression testing. The JUCE plugin integration remains experimental and is not validated for professional real-time audio. The playable desktop experience and mobile app are future goals, not shipped features.

---

## 🎧 What ISLA Does

ISLA explores phase-aligned musical transitions and harmonic smoothing. It detects note boundaries and processes audio through a Python DSP pipeline designed for experimentation and offline workflows.

The available smoothing modes are **Velvet**, **Legato**, and **Melt**. Their musical character is a creative goal; measurable output quality and real-time performance require listening tests and continued validation.

---

## ✨ Features  
- **Phase‑Aligned Note Smoothing** — reduces harsh jumps between notes  
- **Harmonic Blending** — softens overtones for a warm, gradual sound  
- **Boundary Detection** — identifies note transitions in audio   
- **Soft DSP Modes** — customizable smoothing profiles  
- **Python DSL** — expressive commands for musical shaping  
- **Plugin‑Ready Architecture** — can be wrapped into VST/AU later  
- **Minimal Codebase** — easy to fork, extend, and integrate  

---

## 🧠 Why This Exists  
Slowed audio often reveals harsh discontinuities in acoustic instruments—especially piano—where note transitions become abrupt, metallic, or overly resonant. ISLA explores a **continuity layer** that gently smooths these transitions without altering tempo or performance feel.

This project explores a new idea:  
> *What if musical notes could transition with engineered softness, even in instruments that don’t naturally provide it?*

---

## 📦 Installation

Requires Python 3.10+ and the project dependencies. From a local checkout:

```bash
python -m pip install -e .
```

**Compatibility note:** The Python distribution remains `phased-music-notes`, and the import path remains `phased_music_notes` in this branding PR. This avoids breaking existing scripts. The GitHub repository URL and JUCE/plugin identifiers also remain unchanged until a separately reviewed migration.

---

## 🐍 Offline Audio Example

Process a local WAV file using the existing `SmoothPhase` interface:

```python
from phased_music_notes import SmoothPhase

engine = SmoothPhase(mode="velvet")
engine.smooth_file("input.wav", "output_isla.wav")
```

Choose `"velvet"`, `"legato"`, or `"melt"` to explore different transition treatments. Use files you own or have permission to process.

**Implementation note:** `SmoothPhase` exposes `smooth_file(input_path, output_path)`, not `.smooth(...)`; the example above matches the existing code.

---

## 🧭 Roadmap (Proposed — Not Yet Released)

- **BEDROCK 1.0:** Harden numerical DSP correctness and document outstanding streaming/real-time risks.
- **ISLA v3.0.0 — ALIVE:** Explore a Mac-friendly offline audio interface with import, playback, A/B comparison, and export after BEDROCK acceptance.
- **ISLA Mobile / Pocket:** Research a future phone experience; no mobile application is available yet.
- **Real-time plugin:** Requires a separate architectural validation effort and should not be represented as production-ready.

---

## 🤝 Contributing  
Contributions are welcome.  
Feel free to open issues, submit PRs, or propose new smoothing modes.

---

## 📜 License  
MIT License — free to use, modify, and integrate into commercial or personal projects.

---

## 🙏 Acknowledgements

The development of this codebase reflects a collaborative effort across contributors and tools.

Special thanks to Google Jules for delivering the foundational scaffolding for the tests and examples directories. This contribution strengthened the project’s validation layer, improved developer onboarding, and ensured the DSP engine can be exercised deterministically across multiple modes and workflows.

Microsoft Copilot contributed Python logic, architectural guidance, and iterative refinement throughout the design of the DSP modules, the buffer‑based engine, and the cross‑language integration. Its involvement strengthened the determinism of the system, clarified the DSP flow, and accelerated the development of a clean, reproducible, multi‑language architecture.

The core conceptual breakthrough — the Phased‑Music‑Notes architecture, smoothing modes, harmonic blending pipeline, and deterministic DSP design — was developed by Don Feeney, building on the architectural patterns he previously orchestrated in the AeroCam repository. His work established the system’s foundational invariants, cross‑language design, and buffer‑based DSP flow, forming the backbone of the entire engine.

This project embodies team‑oriented engineering: human insight, AI‑accelerated development, and a shared commitment to building robust, expressive audio software.

Last acknowledgment goes to Carmen, Act I: Habanera — the soundtrack that carried the final battle with Windows CI. Fate is a rebellious bird, but deterministic builds win.
