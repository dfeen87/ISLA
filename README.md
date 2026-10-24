# ISLA
### Phase-aligned musical note smoothing · an offline-first audio DSP project

![License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-BEDROCK--baseline-blue)
[![CI](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml)

**ISLA** is the new name for **Phased-Music-Notes**: an experimental audio engineering project exploring smoother transitions between musical notes with phase-aware analysis, transient smoothing, and harmonic blending.

**Dedicated to Isla, the creator's niece.** The name celebrates the idea that music and thoughtful engineering can make expressive moments feel a little softer.

**Current scope:** Offline Python DSP plus the **ISLA v3.0.0 — ALIVE terminal audio MVP** for loaded local recordings on macOS. This is a release target pending acceptance, not a published v3 release. The JUCE plugin remains experimental; mobile and system-wide audio processing are future work.

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

**Codebase identity:** The editable distribution is `isla-audio` and the public Python import is `isla`. The original `phased_music_notes` modules and legacy Python class names remain available for existing integrations. The JUCE build target and plugin product display are now `ISLA`, while original plugin identity codes and protobuf/gRPC wire service identifiers stay unchanged for compatibility. The GitHub repository is now `dfeen87/ISLA`.

### After Cloning — Start ISLA on macOS

Requires Python 3.10+ (`python3 --version`). In Terminal:

```bash
git clone https://github.com/dfeen87/ISLA.git
cd ISLA
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[playback]'
isla
```

These commands install the project, NumPy, SciPy, SoundFile, and the optional
`sounddevice` playback backend. On macOS, the sounddevice pip wheel includes
PortAudio; no DAW, VST, JUCE build, or separate audio driver is required.
See the [backend installation documentation](https://python-sounddevice.readthedocs.io/en/latest/installation.html).
The shell also opens with `python -m isla`. In a later Terminal session, return to
`ISLA` and run `source .venv/bin/activate` before `isla`.

Load your own recording. Quotes handle paths containing spaces; `~` expands to
your home directory. Loading prepares all three modes in a background process.
The prompt remains available; use `status` until `Preparation: Ready` appears,
then play. A request to play before preparation finishes reports its progress.

```text
$ isla
ISLA — ALIVE
Audio Engine: Ready
Status: Idle
Type help for commands.
Output: MacBook Pro Speakers
isla> load "~/Music/my piano.wav"
Loading audio and preparing Velvet, Legato, and Melt. Use status to check progress.
isla> status
File: /Users/you/Music/my piano.wav
Preparation: Ready
Mode: original
Status: stopped
Position: 0.00 / 120.00 s
Output: MacBook Pro Speakers
isla> play
Playing original audio.
isla> mode velvet
VELVET enabled.
isla> mode legato
LEGATO enabled.
isla> mode melt
MELT enabled.
isla> bypass
Original audio enabled.
isla> pause
Playback paused.
isla> play
Playback resumed.
isla> stop
Playback stopped.
isla> exit
Audio stopped.
Resources released.
Goodbye from ISLA.
```

The example file, duration, and output name are illustrative; use a real local path.

| Command | Behavior |
|---|---|
| `load <path>` | Load and prepare a local recording; replaces the previous recording after a valid header check |
| `play` | Start, resume, or restart after completion |
| `pause` | Pause and retain the current position |
| `stop` | Stop and reset position to the beginning |
| `mode velvet` | Select the existing Velvet DSP output |
| `mode legato` | Select the existing Legato DSP output |
| `mode melt` | Select the existing Melt DSP output |
| `bypass` | Select the decoded original recording |
| `status` | Show file, preparation progress, mode, playback state, position, and output |
| `help` | Show commands |
| `exit` | Stop audio, cancel preparation, release resources, and return to Terminal |

Commands and mode names accept uppercase or lowercase. Paths retain their case.
Ctrl-D or Ctrl-C at the prompt also exits and cleans up.

**Formats and output:** WAV is the guaranteed input format, for mono or stereo.
Other formats (such as FLAC/AIFF) depend on the installed libsndfile; MP3 support
is not guaranteed. Sample rate, channel order/count, and sample length are kept;
there is no application resampling or global volume adjustment. Playback uses
float32 samples. Choose your speakers or headphones in **System Settings → Sound
→ Output** before `play`. ISLA opens the default Core Audio output when starting
or resuming; a change during playback may require `stop`, then `play`.

**Troubleshooting:** If the device is unavailable, connect/select an output and
try `play` again. Run `python -m sounddevice` in the activated environment to list
what PortAudio sees. If `status` says playing but you hear nothing, check the
listed output, macOS/app volume, and that the recording contains sound. ISLA does
not change volume settings. If a device rejects a file's sample rate or channel
count, ISLA reports the error; select a compatible output. If playback fails after
a device disconnects, reconnect/select an output, then `stop` and `play`. If the
backend cannot import, rerun `python -m pip install -e '.[playback]'` in the active
virtual environment. Invalid/missing files report an error without terminating
the shell. Preparation errors appear on the next command; load a valid file to retry.

**Beta limits:** All modes are prepared before playback becomes available. Long
recordings take time and require memory for offline DSP plus temporary disk space
for four float32 buffers (about 81 MiB per minute of 44.1 kHz stereo audio).
`status` updates progress and completion when requested. Switching uses a short
5 ms crossfade at an output block boundary while retaining the sample cursor;
sample-perfect gapless operation is not claimed. Pause uses the device clock to
estimate the audible position; hardware latency and scheduling can affect it.
Mode differences depend on detected note boundaries and can be subtle or absent
on sustained tones. This Python output callback is an MVP, not a hard real-time
audio engine. Listening quality and long-session reliability need owner acceptance.

**Loaded files only:** ISLA processes recordings explicitly loaded into it. It does
not intercept Spotify, browsers, games, or other system audio.

For verification results and the exact owner listening checklist, see
[ALIVE implementation and acceptance](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md).
The [BEDROCK invariants](docs/bedrock/1.0/INVARIANT_REGISTER.md),
[validation report](docs/bedrock/1.0/VALIDATION_REPORT.md), and
[remaining DSP/real-time risks](docs/bedrock/1.0/RESIDUAL_RISKS.md) still apply.

---

## 🐍 Offline Audio Example

Process a local WAV file using the existing `SmoothPhase` interface:

```python
from isla import SmoothPhase

engine = SmoothPhase(mode="velvet")
engine.smooth_file("input.wav", "output_isla.wav")
```

Choose `"velvet"`, `"legato"`, or `"melt"` to explore different transition treatments. Use files you own or have permission to process.

**Implementation note:** `SmoothPhase` exposes `smooth_file(input_path, output_path)`, not `.smooth(...)`; the example above matches the existing code.

---

From the command line, you can also use `isla --input input.wav --output output_isla.wav --mode velvet` after installation, or `python -m isla` with the same arguments.

---

**Engineering note:** Existing `phased_music_notes` source files remain the authoritative DSP implementation behind the new `isla` entry points. This avoids duplicating or rewriting BEDROCK-tested audio algorithms. New service discovery reports `isla`; deployments relying on the previous Docker Compose service or HTTP health response must update their configuration.

---

## 🧭 Roadmap (Proposed — Not Yet Released)

- **BEDROCK 1.0:** Established a regression-tested offline DSP foundation and documented outstanding streaming/real-time risks.
- **ISLA v3.0.0 — ALIVE:** Terminal MVP implemented for local-file playback, prepared Velvet/Legato/Melt modes, and bypass comparison; release acceptance remains pending. Offline CLI export remains available.
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
