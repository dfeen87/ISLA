# ISLA — Let the Music Flow.

**ALIVE + LIVE · Velvet · Legato · Melt**

[![Latest Release](https://img.shields.io/github/v/release/dfeen87/ISLA?display_name=tag&style=for-the-badge&logo=github&label=Release&color=8B5CF6)](https://github.com/dfeen87/ISLA/releases/latest)
[![ALIVE Python Acceptance](https://img.shields.io/github/actions/workflow/status/dfeen87/ISLA/alive.yml?branch=main&label=ALIVE%20Tests&style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/dfeen87/ISLA/actions/workflows/alive.yml)
[![Linux JUCE Build](https://img.shields.io/github/actions/workflow/status/dfeen87/ISLA/ci.yml?branch=main&label=Linux%20%2F%20JUCE&style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/dfeen87/ISLA/actions/workflows/ci.yml)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![Experimental LIVE for macOS 13+](https://img.shields.io/badge/LIVE-macOS%2013%2B-111827?style=for-the-badge&logo=apple&logoColor=white)](#live-listen-to-your-mac)
[![MIT License](https://img.shields.io/badge/License-MIT-16A34A?style=for-the-badge)](LICENSE)

**ISLA** is an open-source audio experiment exploring softer, more connected musical transitions through note smoothing and harmonic blending. It is for musicians, curious listeners, and developers who want to listen, compare, and help shape the sound.

Listen to your Mac's audio through **LIVE**, or open a local recording in the **ALIVE** file player. Switch between **Velvet**, **Legato**, **Melt**, and the original sound with **Bypass**, all from the terminal.

**Dedicated to Isla, the creator's niece.** Her name is a reminder that expressive music and thoughtful engineering belong together.

> **Before you begin:** ALIVE and experimental LIVE are implemented on `main`. The checked-in package version is **3.1.1**, released as [v3.1.1 — LIVE Continuity & Recovery](https://github.com/dfeen87/ISLA/releases/tag/v3.1.1) following the published [v3.1.0 — DSP Stability & Hear the Difference](https://github.com/dfeen87/ISLA/releases/tag/v3.1.0). These release tags preserve their respective historical commits. Recovery remains experimental and sustained native Mac acceptance is pending.

**Start here:** [Hear the difference](#hear-the-difference) · [Install ISLA](#get-started-on-macos) · [Mac audio / LIVE](#live-listen-to-your-mac) · [Local files / ALIVE](#alive-play-a-local-audio-file)

**Explore:** [Commands](#terminal-command-reference) · [Troubleshooting](#troubleshooting) · [Privacy and limits](#privacy-and-practical-limits) · [Engineering evidence](#engineering-and-evidence)

---

## What ISLA does

ISLA was inspired by how slowing a piano recording can expose abrupt note attacks and resonances. It explores whether software can make those transitions feel softer and more connected without losing the character of the performance.

**Choose your way to listen:**

| Experience | What you hear | Additional setup |
|---|---|---|
| **LIVE — Mac system audio** | YouTube, browser audio, and other sound sent through ISLA to your speakers/headphones | **BlackHole 2ch** virtual audio device; macOS audio routing |
| **ALIVE — Local file player** | Load a WAV recording, play/pause/stop, compare processing modes and Bypass | No BlackHole required |
| **Offline export** | Process a file and save a new audio file using the existing CLI/Python API | No BlackHole required |

**Three musical modes, plus Bypass**

| Mode | Listening intention |
|---|---|
| **Velvet** | Gentler harmonic texture and less sharp-feeling attacks |
| **Legato** | A more connected musical impression between notes |
| **Melt** | A more pronounced, flowing harmonic texture |
| **Bypass** | The original input audio, without ISLA's smoothing |

These are **creative goals**, not guarantees for every recording. LIVE modes share a continuous harmonic-processing structure and differ by strength; the offline file processor also has look-ahead note-boundary processing. The two pipelines do **not** produce identical results. LIVE changes can sound subtle; compare against Bypass at similar loudness.

Bypass keeps the decoded original in ALIVE and a time-aligned copy of the captured input in LIVE. It does not remove LIVE's monitoring delay. Processing is not loudness-normalized, so a louder mode is not necessarily a better one.

### Why this exists

*What if musical notes could transition with engineered softness, even in instruments that don't naturally provide it?*

ISLA began as **Phased-Music-Notes** and evolved through a regression-tested BEDROCK DSP foundation into a usable terminal player and experimental live-audio monitor.

### Hear the Difference

Compare the same short **Emotional Piano** passage by **triangelx**, published under **CC0**, through the original LIVE DSP baseline. Play or download each FLAC and keep your playback volume fixed:

| Original / Bypass | Velvet · 0.35 | Legato · 0.55 | Melt · 0.75 |
|---|---|---|---|
| [Listen / download](docs/audio/live-baseline/bypass.flac?raw=1) | [Listen / download](docs/audio/live-baseline/velvet.flac?raw=1) | [Listen / download](docs/audio/live-baseline/legato.flac?raw=1) | [Listen / download](docs/audio/live-baseline/melt.flac?raw=1) |

These reference samples retain the original strengths. No mode tuning or audible improvement is claimed. The [source, license and render details](docs/audio/live-baseline/PROVENANCE.md) identify the baseline, passage and level adjustments; the source description does not establish how the instrument was recorded.

The [controlled study](docs/research/live-dsp-study/README.md) found three intensities of one harmonic operation. Explore the [mathematics](docs/research/live-dsp-study/LIVE_DSP_BASELINE_ANALYSIS.md), [same-passage measurements](docs/research/live-dsp-study/MODE_DIFFERENTIATION_RESULTS.md) and [listening guide](docs/research/live-dsp-study/LISTENING_GUIDE.md). Numerical separation does not establish musical quality or preference.

The [numerical robustness corrections and before/after evidence](docs/research/live-dsp-study/IMPLEMENTATION_REVIEW.md) shipped in v3.1.0. The subsequent [bounded capture-loss recovery implementation](docs/alive/capture-recovery/ASSESSMENT.md) is included in the v3.1.1 patch candidate: isolated driver-reported capture loss can recover through safe silence, queue disposal and fresh DSP state while repeated or unsafe faults still stop LIVE. [Native Mac acceptance](docs/alive/capture-recovery/NATIVE_CHECKLIST.md) is pending; uninterrupted audio, restored lost samples, and independent musical retuning are not claimed.

The [native acceptance report](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md) and [owner listening follow-up](docs/alive/OWNER_LISTENING_FOLLOWUP.json) document earlier Mac sessions, including subtle mode differences and a preference for Melt. That historical preference is separate from these samples. No terminal demo GIF or new native listening acceptance is claimed.

---

## Get started on macOS

Use these instructions on a Mac with **Python 3.10+** and Git. LIVE targets macOS **13+**, requires a **separate stereo physical output**, and has been tested on an Apple Silicon Mac; broader compatibility is not yet established. Instructions below assume you clone into your home directory.

### 1. Clone ISLA

In **Terminal**:

~~~bash
cd ~
git clone https://github.com/dfeen87/ISLA.git
cd ISLA
~~~

### 2. Prepare the Python environment

Check your Python version before creating the environment:

~~~bash
python3 --version
~~~

Use **Python 3.10 or newer**. If it is missing or older, install a suitable version from [Python's macOS downloads](https://www.python.org/downloads/macos/), reopen Terminal, return to `~/ISLA`, and check again. Python 3.10/3.13 are covered by the repository's ALIVE CI matrix; the native acceptance report records Python 3.14.6.

Then, from your `ISLA` checkout:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[playback]'
~~~

The editable install provides the `isla` console command, NumPy, SciPy, SoundFile, and the `sounddevice`/PortAudio playback backend. It does **not** install BlackHole. No DAW, VST, or JUCE build is required to run the terminal application.

**Verify that the installation completed successfully** (still at your Mac's shell prompt, with `(.venv)` active):

~~~bash
python -m pip show isla-audio
~~~

You should see package information including `Name: isla-audio`. If the package is not found, check the output of `python -m pip install -e '.[playback]'` and rerun it from `~/ISLA`. Using `python -m pip` installs into the same Python environment you'll use to launch ISLA. A pip `[notice]` suggesting `pip install --upgrade pip` is optional and does not indicate an ISLA installation error.

The environment must be activated in each new Terminal session. To use **local audio files only**, continue to [ALIVE](#alive-play-a-local-audio-file); BlackHole is unnecessary.

## LIVE: Listen to your Mac

Complete the Python setup above first. These steps route browser and other Mac audio through ISLA.

### 1. Install Homebrew if needed, then BlackHole 2ch

LIVE needs a virtual cable between macOS sound and ISLA. **BlackHole 2ch is a virtual audio device, not an app to launch.** ISLA does not install or bundle it.

The recommended route is [Homebrew](https://brew.sh/). Its [current macOS requirements](https://docs.brew.sh/Installation#macos-requirements) are separate from ISLA's macOS 13+ target. Check whether it is installed:

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

### 2. Set up the physical output and BlackHole routing

**Do this before starting LIVE monitoring:**

1. In **System Settings → Sound → Output**, note your **normal physical output** (such as `MacBook Pro Speakers` or `External Headphones`). Set a comfortable volume on that physical device **before** switching outputs.
2. In **Audio MIDI Setup**, set **BlackHole 2ch** to **48,000 Hz / 2 channels**. Use a physical output that supports stereo at the same rate. To use 44,100 Hz instead, match both device formats to that rate and later start with `monitor start 44100`.
3. In **System Settings → Sound → Output**, manually choose **BlackHole 2ch**. **Your Mac may now sound silent: that is expected.** ISLA will be the audio monitor that sends the captured sound to your physical output.
4. **Do not use a Multi-Output or Aggregate Device, or another monitor that also sends the browser audio directly to the speakers.** You could otherwise hear delayed/doubled audio or create a feedback loop.

The intended path is:

~~~text
YouTube / Mac system audio → BlackHole 2ch → ISLA LIVE → physical speakers / headphones
~~~

ISLA deliberately **does not change the macOS default sound output automatically**. You must restore that setting when finished.

### 3. Launch ISLA and confirm Bypass

**First, run these commands in macOS Terminal** (where your shell prompt usually ends in `%` or `$`). Reopen Terminal after the BlackHole restart, if needed:

~~~bash
cd ~/ISLA
source .venv/bin/activate
python -m isla
~~~

**`python -m isla` is the recommended first-run command.** After successful installation, you can also launch with the shorter `isla` console command if it is available in your activated environment.

If you instead enter `isla` and receive `zsh: command not found: isla`, **don't type `devices` into zsh**. Check the installation with `python -m pip show isla-audio`; if the package is missing, run these commands in `~/ISLA`:

~~~bash
python -m pip install -e '.[playback]'
python -m isla
~~~

If the module launches but `isla` is still not found, continue using `python -m isla` and investigate the console-script `PATH` later. If the module does not launch, read its error and recheck the Python environment and installation output.

When ISLA starts successfully, you'll see a message similar to this (your output-device name may differ):

~~~text
ISLA — ALIVE + LIVE
Audio Engine: Ready
Status: Idle
Type help for commands.
Output: External Headphones
isla>
~~~

**First command inside ISLA: `setup audio`.** Once you see the `isla>` prompt, type this command and press Return (type only the command, **not** `isla>`):

~~~text
setup audio
~~~

The guided setup asks you to select **BlackHole 2ch** for capture and then **physical stereo speakers/headphones** for ISLA's playback output. At its `Select input` and `Select output` prompts, enter a listed device number or exact name. For example, select `0` for BlackHole and `1` for External Headphones **only if those numbers appear in your own list**. Type `cancel` to leave without changing the route. **Selecting the physical output inside ISLA is not the same as changing the Mac's system output.** The wizard saves `source system`, input and output inside ISLA, but **does not start monitoring or change macOS Sound settings**. To complete the route, manually select **BlackHole 2ch**, not your physical speakers, in macOS **System Settings → Sound → Output**; ISLA forwards the audio to your selected speakers. The LIVE guard rejects an unconfirmed single-path route rather than risking a duplicate/feedback path.

**Important — two different prompts:**

- **macOS Terminal / zsh:** `(.venv) (base) ... ISLA %` means you are still at your Mac's shell prompt. Running `devices` here produces `zsh: command not found: devices`.
- **ISLA:** `isla>` means the app is running. **Only here** can you use ISLA commands such as `devices`, `source system`, `monitor start`, and `mode melt`.

**Optional — manual device selection:** If you prefer the original commands instead of the wizard, type `devices` at the normal `isla>` prompt to view all devices:

~~~text
devices
~~~

The `devices` command **only displays a list; it does not open a selection menu**. From the normal `isla>` prompt, enter these commands one line at a time, replacing `External Headphones` with your own physical output (for example, `MacBook Pro Speakers`):

~~~text
source system
input "BlackHole 2ch"
output "External Headphones"
~~~

Or use `input 0` and `output 1` **if those are the indices in your current list**. Typing a bare `1`, `1:`, or `External Headphones` at `isla>` does not select a device. Never choose BlackHole as the ISLA output. A startup line such as `Output: BlackHole 2ch` reflects the macOS default output, not your selected physical ISLA output.

**With either setup method**, after confirming macOS **System Settings → Sound → Output** is set to **BlackHole 2ch**, type:

~~~text
bypass
monitor start
status
~~~

Now play music in your browser—for example, [the Beethoven performance used in native testing](https://www.youtube.com/watch?v=UHd8jwXBzXE). This is source material, **not an ISLA before/after demo**. No audio download or WAV file is required. Confirm that **Bypass** is audible through the chosen physical output, with no echo or second unprocessed path. In `status`, look for **Monitor: Running** and nonzero input/output signal levels while music plays.

### 4. Compare Velvet, Legato, Melt and Bypass

Switch profiles while the music plays:

~~~text
mode velvet
mode legato
mode melt
bypass
status
~~~

Allow a passage of music to play in each mode. These profiles change the harmonic processing; the musical effect can be subtle and depends on the material. The terminal remains responsive; `status` reports signal levels, device status and buffer counters. Reported latency is an ADC/DAC **timestamp estimate**, not an independently measured acoustic/video-sync delay.

### 5. Exit and restore normal Mac audio

Inside ISLA:

~~~text
monitor stop
exit
~~~

Pause the browser or music app. Then open **System Settings → Sound → Output** and **manually switch back to the physical output you noted in the routing setup**. ISLA cannot restore a manually changed system device on `exit`. If ISLA crashes, is force-quit, or your Mac becomes silent, reselect your physical output in macOS Sound settings.

**Permissions:** If capture is silent and macOS requests it, allow audio-input/microphone access to Terminal or the app running Python. Check **System Settings → Privacy & Security → Microphone**. LIVE uses BlackHole audio input, **not** screen recording or ScreenCaptureKit. It does not save or transmit captured system audio.

---

## ALIVE: Play a local audio file

**No Homebrew or BlackHole required for this mode.** Complete and verify the Python installation under [Get started](#get-started-on-macos), then select your ordinary speakers/headphones in macOS. In Terminal:

~~~bash
cd ~/ISLA
source .venv/bin/activate
python -m isla
~~~

You can also run `isla` when its installed console command is available.

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

The one-shot file-processing route is available using Python directly:

~~~bash
python -m isla --input input.wav --output output_isla.wav --mode velvet
~~~

When the short `isla` console command is available, `isla --input input.wav --output output_isla.wav --mode velvet` is equivalent.

Or in Python:

~~~python
from isla import SmoothPhase

engine = SmoothPhase(mode="velvet")
engine.smooth_file("input.wav", "output_isla.wav")
~~~

Use `velvet`, `legato`, or `melt`. The API is `smooth_file(input_path, output_path)`. Process recordings you own or have permission to use.

---

## Terminal command reference

| Command | File source (ALIVE) | System source (LIVE) |
|---|---|---|
| `help` / `devices` / `status` / `exit` | Supported | Supported |
| `source file` / `source system` | Switch to file or system source | Switch to file or system source |
| `output "<name or index>"` | Select a device while stopped | Select a **physical** device while stopped |
| `input "BlackHole 2ch"` | Configure capture for LIVE | Select standalone BlackHole 2ch (the default capture name) |
| `load "<path>"` | Load and prepare local audio | Switch to `source file` first |
| `play` / `pause` | Start/resume or pause recording | Control the browser instead |
| `stop` | Stop and reset to beginning | Stops the live monitor |
| `monitor start [44100\|48000]` | Not applicable | Start capture and playback (default 48000); omit brackets when typing |
| `monitor stop` | Stops LIVE monitor if present | Stop LIVE monitoring |
| `mode velvet` / `mode legato` / `mode melt` | Select prepared file processing | Select LIVE harmonic profile |
| `bypass` | Decoded original audio | Original captured system audio, time-aligned |

Commands are case-insensitive where appropriate; file and device names retain their case. `Ctrl-C` or `Ctrl-D` at the terminal prompt also initiates cleanup. Switch devices **only while playback/monitoring is stopped**.

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| **`brew: command not found`** | Install Homebrew from [brew.sh](https://brew.sh/) and follow its post-install shell-path instructions. |
| **BlackHole already installed** | Homebrew's `Not upgrading blackhole-2ch, the latest version is already installed` message is informational. Continue to the audio-device setup. |
| **BlackHole not found** | Install the **2ch** cask, restart macOS, and confirm the device appears in **Audio MIDI Setup**. Run `devices` again in a freshly launched ISLA terminal. |
| **Mac goes silent after selecting BlackHole** | Expected until LIVE is monitoring. If you want ordinary sound back, select your physical speakers/headphones in **System Settings → Sound → Output**. |
| **LIVE is silent** | Confirm YouTube is playing, system output is **BlackHole 2ch**, ISLA input is BlackHole, ISLA output is the correct *physical* device, and input permission/volume are enabled. Use `status` to distinguish silent input from output problems. |
| **Echo, feedback or doubled sound** | Immediately run `monitor stop`. Remove Multi-Output routing, per-app direct speaker output and any other software monitor. Do not choose BlackHole as ISLA output. |
| **Device missing or disconnected** | Run `monitor stop`, reconnect the device, then `devices`; relaunch ISLA if Core Audio/PortAudio holds stale device information. No silent device fallback is provided. |
| **Crackling, glitches or noticeable delay** | Prefer built-in or wired speakers to Bluetooth, close busy apps, check matching 44.1/48 kHz device formats, and review `status` for underflows, overflows or device warnings. |
| **`zsh: command not found: isla`** | At the Mac's shell prompt, run `cd ~/ISLA`, `source .venv/bin/activate`, and `python -m pip show isla-audio`. If the package is missing, rerun `python -m pip install -e '.[playback]'`. Start with `python -m isla` and enter `devices` **only after** the `isla>` prompt appears. |
| **File won't load/play** | Use a valid WAV path, wait for `Preparation: Ready`, check the physical output device and sample-rate/channel support. |

For deeper device diagnostics inside the activated environment, try `python -m sounddevice`. See [ALIVE/LIVE implementation and acceptance](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md) for native test details and unresolved risks.

---

## Privacy and practical limits

- **Local processing:** The terminal player processes audio on your Mac without an account or cloud processing. LIVE keeps captured audio in memory and does not save or transmit it. ALIVE writes the decoded original and three prepared modes to an owned local temporary directory, removed on replacement or normal exit; forced termination can leave temporary files behind. Offline export writes the output file you request. Streaming sites and dependency installers have their own network behavior.
- **Experimental LIVE:** This Python/PortAudio implementation is not hard real-time. It targets macOS 13+ with standalone **BlackHole 2ch** and a **separate physical stereo output** at 44.1 or 48 kHz. Native evidence comes from one Apple Silicon Mac; it does not establish compatibility with every Mac, output device or OS version. Wired outputs avoid the extra delay associated with Bluetooth.
- **Latency and buffers:** The LIVE DSP adds **32.00 ms at 48 kHz / 34.83 ms at 44.1 kHz**, plus queues and device latency. Native test sessions reported roughly **79–107 ms** in ADC/DAC timestamp estimates, not independent acoustic measurements. Bypass shares the processing delay; video sync can be affected. Fixed buffers can run dry and emit silence, while capture/ring failures can stop monitoring. Check `status` for counters and errors. There is no user-facing buffer-size command.
- **Routing and recovery:** ISLA rejects virtual, Aggregate and Multi-Output sinks for LIVE, but cannot detect every other app's monitoring path. It does not change the Mac's system output or reconnect devices automatically. Stop monitoring before changing devices, and restore normal output in macOS when finished.
- **Local files:** ALIVE prepares whole files before playback and needs working memory and temporary disk space. WAV mono/stereo is the guaranteed format; other formats depend on libsndfile. Sample-perfect gapless switching is not promised. Neither path loudness-normalizes the modes; output conversion or hardware can clip levels.
- **Release status:** Python package, HTTP service and JUCE/CMake metadata are aligned at **3.1.1**. The [v3.0.0 — ALIVE + LIVE](https://github.com/dfeen87/ISLA/releases/tag/v3.0.0), [v3.1.0 — DSP Stability](https://github.com/dfeen87/ISLA/releases/tag/v3.1.0) and [v3.1.1 — LIVE Continuity & Recovery](https://github.com/dfeen87/ISLA/releases/tag/v3.1.1) releases are published from separate pinned commits. Software checks alone do not establish native release acceptance of recovery. Longer-session, stress, physical-disconnect and broader hardware acceptance remain pending. Desktop GUI and mobile apps are future work; the JUCE plugin remains experimental.

## Engineering and evidence

**LIVE** uses a continuous harmonic-processing path with retained weighted overlap-add (WOLA) state, a 2048-sample window / 512-sample hop, short mode crossfades and a time-aligned Bypass. Spectral work runs outside the audio callback. **ALIVE and offline export** use the existing whole-file note-boundary and harmonic pipeline. Those pipelines have different behavior; passing offline numerical checks does not establish professional real-time readiness.

The public Python package is `isla`, and the distribution is `isla-audio`. Legacy `phased_music_notes` imports and aliases remain available. The gRPC wire service identifiers and JUCE plugin identity codes remain intact; some Docker/service discovery identifiers have changed to ISLA.

**Engineering evidence and source of truth**

These records preserve the versions and procedures used during their original tests, including the earlier `2.1.0` baseline. Use the onboarding above for current setup.

- [ALIVE + LIVE implementation, native acceptance and remaining gates](docs/alive/IMPLEMENTATION_AND_ACCEPTANCE.md)
- [Controlled LIVE DSP study: baseline mathematics, same-passage comparisons and open acceptance gates](docs/research/live-dsp-study/README.md)
- Native LIVE transcripts and measurements: [48 kHz](docs/alive/NATIVE_48000.json), [44.1 kHz](docs/alive/NATIVE_44100.json), [stream identity checks](docs/alive/NATIVE_STREAM_IDENTITY.json), and [initial unsuccessful attempts](docs/alive/NATIVE_INITIAL_ATTEMPTS.json)
- [Latest owner listening follow-up](docs/alive/OWNER_LISTENING_FOLLOWUP.json) and [worker-only benchmark, not end-to-end latency](docs/alive/LIVE_BENCHMARK.json)
- [BEDROCK invariant register](docs/bedrock/1.0/INVARIANT_REGISTER.md)
- [BEDROCK validation report](docs/bedrock/1.0/VALIDATION_REPORT.md)
- [BEDROCK residual DSP and real-time risks](docs/bedrock/1.0/RESIDUAL_RISKS.md)
- [BEDROCK release recommendation: no-go for professional real-time audio](docs/bedrock/1.0/RELEASE_RECOMMENDATION.md)
- [ALIVE Python acceptance workflow](.github/workflows/alive.yml) and [Linux/JUCE build workflow](.github/workflows/ci.yml)
- [sounddevice installation details](https://python-sounddevice.readthedocs.io/en/latest/installation.html)
- [BlackHole driver information](https://github.com/ExistentialAudio/BlackHole)

### What's next

- **BEDROCK foundation:** Regression-tested offline numerical invariants and documented streaming/real-time risks.
- **ALIVE + LIVE v3.0.0:** Published milestone for terminal file playback and experimental Mac system-audio monitoring; its release commit is preserved.
- **DSP stability v3.1.0:** Published numerical LIVE reconstruction robustness corrections, reproducible listening comparisons and improved guided setup; its release commit is preserved.
- **LIVE recovery v3.1.1:** Published bounded capture-discontinuity recovery and expanded diagnostics; sustained native Mac recovery acceptance remains pending.
- **Future work:** Distinctive musical-mode tuning, longer-session reliability, graphical Mac experience, mobile research, and separate production-grade plugin validation.

---


## 🤝 Contributing  
Contributions are welcome.  
Feel free to open issues, submit PRs, or propose new smoothing modes.

---

## 📜 License  
[MIT License](LICENSE) — free to use, modify, and integrate into commercial or personal projects under its terms.

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
