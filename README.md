# ISLA
### Phase-aligned musical note smoothing · an offline-first audio DSP project

![License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-BEDROCK--baseline-blue)
[![CI](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml)

**ISLA** is the new name for **Phased-Music-Notes**: an experimental audio engineering project exploring smoother transitions between musical notes with phase-aware analysis, transient smoothing, and harmonic blending.

**Dedicated to Isla, the creator's niece.** The name celebrates the idea that music and thoughtful engineering can make expressive moments feel a little softer.

**Current scope:** Offline Python DSP plus the **ALIVE + LIVE terminal MVP**: local-file playback and experimental macOS system-audio monitoring through separately installed BlackHole 2ch. LIVE provides continuous Velvet/Legato/Melt harmonic profiles and Bypass. v3.0.0 remains a release target pending owner acceptance, not a published version. The JUCE plugin remains experimental; mobile is future work.

---

## 🎧 What ISLA Does

ISLA explores phase-aligned musical transitions and harmonic smoothing. It detects note boundaries and processes audio through a Python DSP pipeline designed for experimentation and offline workflows.

The available smoothing modes are **Velvet**, **Legato**, and **Melt**. Their musical character is a creative goal; measurable output quality and real-time performance require listening tests and continued validation.

---

## ✨ Features  
- **Phase‑Aligned Note Smoothing** — reduces harsh jumps between notes  
- **Harmonic Blending** — softens overtones for a warm, gradual sound  
- **Boundary Detection** — identifies note transitions in audio   
- **ALIVE file player** — prepare a local recording, play/pause/stop, compare modes and Bypass
- **Experimental LIVE monitoring** — YouTube/system audio via BlackHole 2ch, explicit physical output, bounded worker DSP
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
PortAudio; no DAW, VST, JUCE build, or separate audio driver is required for local-file playback. LIVE additionally requires BlackHole 2ch, installed separately below.
See the [backend installation documentation](https://python-sounddevice.readthedocs.io/en/latest/installation.html).
The shell also opens with `python -m isla`. In a later Terminal session, return to
`ISLA` and run `source .venv/bin/activate` before `isla`.

Load your own recording. Quotes handle paths containing spaces; `~` expands to
your home directory. Loading prepares all three modes in a background process.
The prompt remains available; use `status` until `Preparation: Ready` appears,
then play. A request to play before preparation finishes reports its progress.

```text
$ isla
ISLA — ALIVE + LIVE
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
→ Output** before `play`, or use `devices`, then `output "Exact device name"`
while stopped. Without an explicit selection ISLA opens the default output when
starting or resuming; a change during playback may require `stop`, then `play`.

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

**File source:** The commands above process loaded recordings. Use the separate
LIVE source below for browser and Mac system audio; file preparation stays offline.

### LIVE Mode — Process YouTube and Mac System Audio

**Experimental MVP, not a released v3.0.0 or professional low-latency engine.**
Target configuration: macOS 13+, Python 3.10+, standalone **BlackHole 2ch** input,
and a separate stereo built-in, wired/USB, or Bluetooth physical output at **44.1
or 48 kHz**. Native evidence and remaining acceptance items are in the
[ALIVE/LIVE acceptance report](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md).
Bluetooth adds device latency. AirPlay, Aggregate and Multi-Output devices are
rejected as LIVE outputs. Mono DSP is tested; this two-channel capture adapter
requires a stereo output and does not silently downmix.

1. **Install the audio backend** using the virtual environment from the local-file
   instructions above: `python -m pip install -e '.[playback]'`. There are no new
   Python LIVE dependencies. This install path was exercised in a fresh environment.
2. **Install BlackHole separately.** ISLA does not install or bundle a driver.
   Use the [official installer](https://existential.audio/blackhole/), or, if
   Homebrew is already installed, `brew install blackhole-2ch`. This is the
   [vendor's documented command](https://github.com/ExistentialAudio/BlackHole#installation-instructions),
   also used by the owner on the native test Mac. Finish the installer and restart
   if prompted. BlackHole appears as an audio device, not an application. If it is
   installed but missing, restart the Mac before continuing; an administrator can
   instead restart Core Audio, which interrupts current sound.
3. **Permissions:** allow microphone/audio-input access for Terminal (or the host
   application running Python) when macOS asks. Check **System Settings → Privacy
   & Security → Microphone** if capture is silent. This implementation uses an
   audio-input driver, not ScreenCaptureKit; it requests no screen recording.
4. Open **Applications → Utilities → Audio MIDI Setup → Window → Show Audio
   Devices**. Select BlackHole 2ch and set **Format** to **48,000 Hz, 2 channels**.
   Set your speakers/wired output to 48,000 Hz too where available. For 44.1 kHz,
   set both to 44,100 and use `monitor start 44100`. ISLA checks stream support;
   Core Audio may convert device-native formats. There is no Python resampler.
5. Note your normal **System Settings → Sound → Output** choice so you can restore
   it. Then **manually choose BlackHole 2ch as the Mac sound output**. Do **not**
   create or select a Multi-Output device. Sound becomes silent until ISLA monitors
   it. The one listening path must be:
   **YouTube → BlackHole 2ch → ISLA → speakers/headphones**. Disable other software
   monitors and per-app output overrides. A browser routed separately to speakers
   would bypass this path; ISLA cannot inspect every application's settings.
6. In Terminal, return to the checkout, run `source .venv/bin/activate`, then `isla`.
   Run `devices` and copy the exact device names (or indices). Run `source system`,
   `input "BlackHole 2ch"`, and `output "MacBook Pro Speakers"`. For a sound system
   plugged into the Mac headphone jack, macOS may call it **External Headphones**:
   use `output "External Headphones"`. Select the physical listening device here,
   even though the Mac's *system* output remains BlackHole.
7. Run `bypass`, then `monitor start`. The terminal remains usable. Open YouTube
   in your browser and play a solo-piano performance—no download or WAV import.
   For example, [Beethoven played by Valentina Lisitsa](https://www.youtube.com/watch?v=UHd8jwXBzXE).
   First confirm clear Bypass audio with no doubling or feedback.
8. Run `mode velvet`, `mode legato`, `mode melt`, then `bypass` to compare.
   These are **genuine continuous harmonic transformations**, with increasing
   spectral smoothing strengths. They do not reproduce the file player's
   look-ahead note-boundary interpolation. All modes retain window/overlap state;
   Bypass has the same delay, and changes use a 5 ms crossfade.
9. Run `status` to see routing, mode, monitor state, rate, input/output RMS levels,
   buffer counters and an ADC/DAC timestamp latency estimate. The estimate is not
   an acoustic measurement; it excludes browser decoding and may omit device
   processing. Expect a noticeable delay. See the measured results in the report.
10. Run `monitor stop`, pause YouTube, and `exit`. Ctrl-C/Ctrl-D at the prompt
    also stops audio and releases the worker/device. `source file` stops LIVE
    and returns to the retained local-file player; use `load` and `play` normally.
11. **Restore normal Mac sound:** in **System Settings → Sound → Output**, select
    your original speakers/headphones/sound system again, then resume the browser.
    ISLA never changes this system preference itself, so it cannot restore your
    manually chosen route on exit. If sound is silent after stopping, exiting,
    crashing, or force-quitting, select the physical output manually. Restoration
    after a crash or forced termination is never guaranteed.

Example command sequence exercised with native Core Audio (device names are
machine-specific; use `devices`):

```text
$ isla
ISLA — ALIVE + LIVE
Audio Engine: Ready
isla> devices
isla> source system
isla> input "BlackHole 2ch"
isla> output "External Headphones"
isla> bypass
isla> monitor start
LIVE monitoring active.
isla> mode velvet
VELVET enabled (LIVE harmonic profile).
isla> mode legato
LEGATO enabled (LIVE harmonic profile).
isla> mode melt
MELT enabled (LIVE harmonic profile).
isla> bypass
Original system audio enabled.
isla> status
Source: System Audio
Mode: Bypass
Monitor: Running
Input: BlackHole 2ch
Output: External Headphones
isla> monitor stop
LIVE monitoring stopped.
isla> exit
Audio stopped.
Resources released.
Goodbye from ISLA.
```

| Additional command | Behavior |
|---|---|
| `devices` | List input/output devices, channel counts and default rates |
| `source system` | Stop the file player and select LIVE; defaults to BlackHole 2ch capture |
| `input <name or id>` | Explicit capture choice; standalone BlackHole 2ch is required |
| `output <name or id>` | Explicit output selection for either source, while stopped |
| `monitor start [44100 or 48000]` | Open safe capture and physical playback, default 48000 Hz |
| `monitor stop` or LIVE `stop` | Stop worker/stream and discard pending audio |
| `source file` | Stop LIVE and return to local-file commands |
| `mode`, `bypass`, `status`, `help`, `exit` | Work with the selected source |

**LIVE troubleshooting**

- **Silence:** verify YouTube is playing and unmuted; Mac *system* output is
  BlackHole 2ch; ISLA input is BlackHole; ISLA output is the device you actually
  listen through. A plugged-in sound system can be named External Headphones.
  Check that physical device's volume using macOS controls *before* selecting
  BlackHole. `status` RMS values near zero indicate silent capture; nonzero input
  and output with no sound points to output choice/volume. Check audio-input
  permission, BlackHole volume and 2-channel format in Audio MIDI Setup.
- **Echo, doubled audio or feedback:** `monitor stop` immediately. Select standalone
  BlackHole as system output and a separate physical ISLA output. Remove
  Multi-Output/direct-speaker duplication, other monitors and per-app routing
  overrides. Never select BlackHole as ISLA output. ISLA rejects virtual and
  aggregate outputs and checks the default route before opening and every 250 ms.
- **Missing device / device disconnected:** complete driver setup and restart if
  required. Stop audio, reconnect, run `devices`, and select exact names again.
  If Core Audio/PortAudio retains stale device information or reports an internal
  audio-unit error, `exit` and relaunch ISLA to refresh the device inventory.
  No automatic fallback to another output occurs.
- **Delayed or glitching playback:** try wired/built-in output rather than
  Bluetooth; close busy applications and use matching 44.1/48 kHz formats.
  Bypass deliberately keeps DSP alignment delay. Startup discards eight blocks
  (about 85–93 ms) while devices settle. Output starvation emits silence; repeated
  starvation, capture discontinuity, or buffer overflow stops monitoring rather
  than allowing an ever-growing delay. Read the error and retry `monitor start`.
- **Changing devices:** run `monitor stop` before `input` or `output`; use
  `monitor start` afterward. `pause`/`play` belong to the file player; LIVE uses
  `monitor stop`/`monitor start` and the browser's own pause control.

**LIVE beta limits:** Python/GIL scheduling is not hard real-time. Two bounded
8-block rings and fixed WOLA state limit accumulation; startup/status counters
can include device synchronization events. Retained algorithmic delay is 32 ms
at 48 kHz or 34.83 ms at 44.1 kHz, plus transport buffers and hardware latency.
The native/owner test status, glitches, and measured estimates are reported
honestly below. Listening quality, long sessions and all hardware configurations
still require acceptance. Capture stays local in bounded memory: LIVE has no
recording, file-save, or network-transmission feature.

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
- **ISLA v3.0.0 — LIVE:** Experimental BlackHole system-audio capture, explicit physical output, continuous harmonic profiles and Bypass implemented; native/owner evidence and remaining limits are tracked in the acceptance report. No release/tag is published.
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
