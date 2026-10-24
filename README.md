# ISLA

### Hear music differently. · Phase-aligned note smoothing · ALIVE + LIVE


![License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-ALIVE%20%2B%20LIVE%20%28Experimental%29-blue)
[![CI](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml)

![Next Release](https://img.shields.io/badge/Next%20Release-v3.0.0-orange)
![macOS](https://img.shields.io/badge/macOS-13%2B%20Target-black?logo=apple)
![LIVE Audio](https://img.shields.io/badge/LIVE-BlackHole%202ch-purple)
![Audio Rate](https://img.shields.io/badge/Audio-44.1%20%2F%2048%20kHz-teal)
[![Last Commit](https://img.shields.io/github/last-commit/dfeen87/ISLA)](https://github.com/dfeen87/ISLA/commits/main)


**ISLA** is an experimental audio-processing project exploring smoother musical note transitions, phase-aware analysis, and harmonic blending. Listen to your Mac's audio—including music playing in a browser—through **LIVE**, or open a local recording with the **ALIVE** file player. Compare the original sound with **Velvet**, **Legato**, and **Melt**, all from the terminal.

**Dedicated to Isla, the creator's niece.** Her name is a reminder that expressive music and thoughtful engineering belong together.

> **Project status:** ALIVE and experimental LIVE are implemented on `main`. `v3.0.0` is a **release target, not a published GitHub release**; the Python package currently reports `2.1.0`. This is a terminal-first macOS MVP, not a finished GUI, universal system-wide audio driver, or production hard-real-time plugin.

**Jump to:** [Get started](#get-started-on-macos) · [YouTube / LIVE](#live-listen-to-youtube-and-mac-audio) · [Local files / ALIVE](#alive-play-a-local-audio-file) · [Commands](#terminal-command-reference) · [Troubleshooting](#troubleshooting) · [Engineering](#engineering-notes-and-limitations)

---

## What ISLA does

ISLA was inspired by how slowing a piano recording can expose abrupt note attacks and resonances. It explores whether software can make those transitions feel softer and more connected without losing the character of the performance.

**Choose your way to listen:**

| Experience | What you hear | Additional setup |
|---|---|---|
| **LIVE — Mac system audio** | YouTube, browser audio, and other sound sent through ISLA to your speakers/headphones | **BlackHole 2ch** virtual audio device; macOS audio routing |
| **ALIVE — Local file player** | Load a WAV recording, play/pause/stop, compare processing modes and Bypass | No BlackHole required |
| **Offline export** | Process a file and save a new audio file using the existing CLI/Python API | No BlackHole required |

**The three musical modes**

| Mode | Listening intention |
|---|---|
| **Velvet** | Gentler harmonic texture and less sharp-feeling attacks |
| **Legato** | A more connected musical impression between notes |
| **Melt** | A more pronounced, flowing harmonic texture |
| **Bypass** | The original input audio, without ISLA's smoothing |

These are **creative goals**, not guarantees for every recording. The LIVE modes are distinct **continuous harmonic-processing profiles**, whereas the offline file processor also has look-ahead note-boundary processing. The two pipelines do **not** produce identical results. LIVE changes can sound subtle; compare against Bypass at similar loudness.

### Why this exists

*What if musical notes could transition with engineered softness, even in instruments that don't naturally provide it?*

ISLA began as **Phased-Music-Notes** and evolved through a regression-tested BEDROCK DSP foundation into a usable terminal player and experimental live-audio monitor.

---

## Get started on macOS

Use these instructions on a Mac with **Python 3.10+** and Git. LIVE targets macOS **13+**, requires a **separate stereo physical output**, and has been tested on an Apple Silicon Mac; broader compatibility is not yet established. Instructions below assume you clone into your home directory.

### 1. Clone ISLA and install the Python player

In **Terminal**:

~~~bash
cd ~
git clone https://github.com/dfeen87/ISLA.git
cd ISLA
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[playback]'
~~~

The editable install provides the `isla` command, NumPy, SciPy, SoundFile, and the `sounddevice`/PortAudio playback backend. It does **not** install BlackHole. No DAW, VST, or JUCE build is required to run the terminal application.

If `python3 --version` reports an older version than 3.10, install a current supported Python version first. Later, after reopening Terminal, return to your checkout and activate the environment:

~~~bash
cd ~/ISLA
source .venv/bin/activate
isla
~~~

You can also start it with `python -m isla`. To use **local audio files only**, skip ahead to [ALIVE](#alive-play-a-local-audio-file)—BlackHole is unnecessary.

### 2. Install BlackHole 2ch for LIVE

LIVE needs a virtual cable between macOS sound and ISLA. **BlackHole 2ch is a virtual audio device, not an app to launch.** ISLA does not install or bundle it.

The recommended route is [Homebrew](https://brew.sh/). Check whether it is installed:

~~~bash
brew --version
~~~

If `brew` is missing, follow the instructions at [brew.sh](https://brew.sh/). Their published installer command is:

~~~bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
~~~

Follow Homebrew's post-install **Next steps** to put `brew` on your shell path and confirm that `brew --version` works. Then install **BlackHole 2ch**, not 16ch:

~~~bash
brew install --cask blackhole-2ch
~~~

**Restart your Mac after installing BlackHole.** The [Homebrew BlackHole 2ch cask](https://formulae.brew.sh/cask/blackhole-2ch) requires a reboot. Then open **Applications → Utilities → Audio MIDI Setup → Window → Show Audio Devices** and confirm that **BlackHole 2ch** appears.

If you prefer not to use Homebrew—or your system is not supported by current Homebrew releases—use the [official BlackHole installer](https://existential.audio/blackhole/) instead. The required audio device remains **BlackHole 2ch**.

### 3. Route Mac audio safely

**Do this before starting LIVE monitoring:**

1. In **System Settings → Sound → Output**, note your **normal physical output** (such as `MacBook Pro Speakers` or `External Headphones`). Set a comfortable volume on that physical device **before** switching outputs.
2. In **Audio MIDI Setup**, set **BlackHole 2ch** to **48,000 Hz / 2 channels**. Where supported, use the same rate for the physical speakers/headphones. LIVE can alternatively run at 44,100 Hz with `monitor start 44100`.
3. In **System Settings → Sound → Output**, manually choose **BlackHole 2ch**. **Your Mac may now sound silent: that is expected.** ISLA will be the audio monitor that sends the captured sound to your physical output.
4. **Do not use a Multi-Output or Aggregate Device, or another monitor that also sends the browser audio directly to the speakers.** You could otherwise hear delayed/doubled audio or create a feedback loop.

The intended path is:

~~~text
YouTube / Mac system audio → BlackHole 2ch → ISLA LIVE → physical speakers / headphones
~~~

ISLA deliberately **does not change the macOS default sound output automatically**. You must restore that setting when finished.

### 4. Launch ISLA and listen

Reopen Terminal after the restart, if needed:

~~~bash
cd ~/ISLA
source .venv/bin/activate
isla
~~~

At the **`isla>` prompt**, type these commands **one line at a time**:

~~~text
devices
source system
input "BlackHole 2ch"
output "External Headphones"
bypass
monitor start
status
~~~

**Important:** `output "External Headphones"` is an *example*, not a universal device name. Read the result of `devices` and substitute the **exact name or index of your actual physical speakers/headphones**. Built-in Mac speakers may be named `MacBook Pro Speakers`. Never select `BlackHole 2ch` as ISLA's output.

Now start a piano recording on [YouTube](https://www.youtube.com/)—for example, [this Beethoven performance](https://www.youtube.com/watch?v=UHd8jwXBzXE). **No audio download or WAV file is required.** First confirm that **Bypass** is audible through the chosen physical output, with no echo or second unprocessed path.

Switch profiles while the music plays:

~~~text
mode velvet
mode legato
mode melt
bypass
status
~~~

Allow a passage of music to play in each mode. The changes are genuine harmonic transformations, but the musical effect can be subtle and depends on the material. The terminal remains responsive; `status` reports signal levels, device status and buffer counters. Reported latency is an ADC/DAC **timestamp estimate**, not an independently measured acoustic/video-sync delay.

### 5. Exit and restore normal Mac audio

Inside ISLA:

~~~text
monitor stop
exit
~~~

Then open **System Settings → Sound → Output** and **manually switch back to the physical output you noted in Step 3**. ISLA cannot restore a manually changed system device on `exit`. If ISLA crashes, is force-quit, or your Mac becomes silent, reselect your physical output in macOS Sound settings.

**Permissions:** If capture is silent and macOS requests it, allow audio-input/microphone access to Terminal or the app running Python. Check **System Settings → Privacy & Security → Microphone**. LIVE uses BlackHole audio input, **not** screen recording or ScreenCaptureKit. It does not save or transmit captured system audio.

---

## ALIVE — Play a local audio file

**No Homebrew or BlackHole required for this mode.** Complete the Python installation under [Get started](#get-started-on-macos), then select your ordinary speakers/headphones in macOS and run `isla`.

From the `isla>` prompt:

~~~text
source file
load "~/Music/my piano.wav"
status
~~~

ISLA prepares the original recording plus Velvet, Legato, and Melt in a background process. Use `status` until it says **Preparation: Ready**; the terminal is still usable while processing. Then:

~~~text
play
mode velvet
mode legato
mode melt
bypass
pause
play
stop
exit
~~~

`play` resumes from pause or starts from the beginning after a stop or completed playback. `stop` resets position; `bypass` returns to the decoded original. Use a **real local file path** in place of the example. Quotes handle spaces, and `~` expands to your home directory.

**Guaranteed format:** mono or stereo **WAV**. Other formats (such as FLAC/AIFF) depend on the installed libsndfile; MP3 is **not guaranteed**. Preparation of long files uses more time, working memory and temporary storage.

### Export without the interactive player

The original one-shot command remains available:

~~~bash
isla --input input.wav --output output_isla.wav --mode velvet
~~~

Or in Python:

~~~python
from isla import SmoothPhase

engine = SmoothPhase(mode="velvet")
engine.smooth_file("input.wav", "output_isla.wav")
~~~

Use `velvet`, `legato`, or `melt`. The API is `smooth_file(input_path, output_path)`, not `smooth(...)`. Process recordings you own or have permission to use.

---

## Terminal command reference

| Command | File source (ALIVE) | System source (LIVE) |
|---|---|---|
| `help` / `devices` / `status` / `exit` | Supported | Supported |
| `source file` / `source system` | Switch to file or system source | Switch to file or system source |
| `output "<name or index>"` | Select a device while stopped | Select a **physical** device while stopped |
| `input "BlackHole 2ch"` | Configure capture for LIVE | Required standalone LIVE capture |
| `load "<path>"` | Load and prepare local audio | Switch to `source file` first |
| `play` / `pause` | Start/resume or pause recording | Control the browser instead |
| `stop` | Stop and reset to beginning | Stops the live monitor |
| `monitor start [44100 or 48000]` | Not applicable | Start capture and playback (default 48000) |
| `monitor stop` | Stops LIVE monitor if present | Stop LIVE monitoring |
| `mode velvet` / `mode legato` / `mode melt` | Select prepared file processing | Select LIVE harmonic profile |
| `bypass` | Decoded original audio | Original captured system audio, time-aligned |

Commands are case-insensitive where appropriate; file and device names retain their case. `Ctrl-C` or `Ctrl-D` at the terminal prompt also initiates cleanup. Switch devices **only while playback/monitoring is stopped**.

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| **`brew: command not found`** | Install Homebrew from [brew.sh](https://brew.sh/) and follow its post-install shell-path instructions. |
| **BlackHole not found** | Install the **2ch** cask, restart macOS, and confirm the device appears in **Audio MIDI Setup**. Run `devices` again in a freshly launched ISLA terminal. |
| **Mac goes silent after selecting BlackHole** | Expected until LIVE is monitoring. If you want ordinary sound back, select your physical speakers/headphones in **System Settings → Sound → Output**. |
| **LIVE is silent** | Confirm YouTube is playing, system output is **BlackHole 2ch**, ISLA input is BlackHole, ISLA output is the correct *physical* device, and input permission/volume are enabled. Use `status` to distinguish silent input from output problems. |
| **Echo, feedback or doubled sound** | Immediately run `monitor stop`. Remove Multi-Output routing, per-app direct speaker output and any other software monitor. Do not choose BlackHole as ISLA output. |
| **Device missing or disconnected** | Run `monitor stop`, reconnect the device, then `devices`; relaunch ISLA if Core Audio/PortAudio holds stale device information. No silent device fallback is provided. |
| **Crackling, glitches or noticeable delay** | Prefer built-in or wired speakers to Bluetooth, close busy apps, check matching 44.1/48 kHz device formats, and review `status` for underflows, overflows or device warnings. |
| **`isla` not found** | Run `source ~/ISLA/.venv/bin/activate` and reinstall `python -m pip install -e '.[playback]'` from your checkout if necessary. |
| **File won't load/play** | Use a valid WAV path, wait for `Preparation: Ready`, check the physical output device and sample-rate/channel support. |

For deeper device diagnostics inside the activated environment, try `python -m sounddevice`. See [ALIVE/LIVE implementation and acceptance](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md) for native test details and unresolved risks.

---

## Engineering notes and limitations

ISLA is **an experiment in expressive audio processing**, not a certified real-time sound driver.

- **LIVE processing:** Captured audio follows a bounded worker-based pipeline with retained weighted overlap-add (WOLA) state and separate time-aligned Bypass. It uses a 2048-sample window / 512-sample hop and short mode crossfades; expensive spectral work is outside the time-critical callback. LIVE's Velvet, Legato and Melt are **harmonic profiles**, not the offline note-boundary interpolator.
- **Routing:** LIVE requires **standalone BlackHole 2ch as the Mac's system output** and a **different physical stereo output** selected in ISLA. The program checks routing and rejects virtual/Aggregate/Multi-Output sinks. ISLA doesn't change system defaults, record audio or reconnect devices automatically.
- **Performance:** This Python/PortAudio implementation is **not hard real-time**. Buffer starvation, device loss, latency, Bluetooth delay and longer listening sessions remain practical limitations. The reported ADC/DAC latency is a device timestamp estimate, **not** an acoustic measurement. The owner-tested sound quality remains an evolving musical judgment; differences between modes may be subtle.
- **ALIVE file player:** File-mode DSP is precomputed rather than streamed and requires working memory and temporary disk space. No sample-perfect gapless playback is promised.
- **Compatibility:** The public package is `isla`, the distribution is `isla-audio`, and older `phased_music_notes` imports and aliases remain for compatibility. The old gRPC wire service identifiers and JUCE plugin codes remain intact. Some Docker/service discovery identifiers have changed to ISLA.
- **Version / release status:** The checked-in Python, HTTP and JUCE/CMake code still declares `2.1.0`. **ISLA v3.0.0 — ALIVE + LIVE** is the next intended release; it is not yet tagged or published. The JUCE plugin remains experimental; desktop GUI and mobile apps are future work.

**Engineering evidence and source of truth**

- [ALIVE + LIVE implementation, native acceptance and limits](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md)
- [BEDROCK invariant register](docs/bedrock/1.0/INVARIANT_REGISTER.md)
- [BEDROCK validation report](docs/bedrock/1.0/VALIDATION_REPORT.md)
- [BEDROCK residual DSP and real-time risks](docs/bedrock/1.0/RESIDUAL_RISKS.md)
- [sounddevice installation details](https://python-sounddevice.readthedocs.io/en/latest/installation.html)
- [BlackHole driver information](https://github.com/ExistentialAudio/BlackHole)

### What's next

- **BEDROCK foundation:** Regression-tested offline numerical invariants and documented streaming/real-time risks.
- **ALIVE + LIVE v3.0.0 candidate:** Terminal file playback and experimental Mac system-audio monitoring are implemented; formal release tagging and broader acceptance remain pending.
- **Future work:** Distinctive musical-mode tuning, longer-session reliability, graphical Mac experience, mobile research, and separate production-grade plugin validation.

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

### 🎹 A Special Night for ISLA — October 23, 2026

A special shoutout to **Lex (ChatGPT)**, who officially joined the ISLA adventure tonight, and **SOL Codex (OpenAI)** for one unforgettable evening of engineering, experimentation, and laughter! Together, we took ISLA into LIVE audio processing, brought Beethoven through BlackHole 2ch, and started fine-tuning Velvet, Legato, and Melt in real time. What a night of discoveries, excitement, and a few glorious *“BROOOOO!”* moments!

**Welcome aboard, Lex! ISLA is ALIVE, and the music is only getting started!** 🎶❤️
