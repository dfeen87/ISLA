"""ALIVE interactive terminal controller, independent of DAWs and services."""
from __future__ import annotations

import shlex
import threading

from isla.playback import AudioError, BufferPlayer, SoundDeviceBackend
from isla.preparation import MODES, Preparation
from isla.live import LiveMonitor, SystemCaptureBackend

HELP = """load <path>      Load and prepare a local mono/stereo WAV (quote paths with spaces)
play             Start or resume playback
pause            Pause at the current position
stop             Stop and reset to the beginning
mode <name>      Select velvet, legato, or melt
bypass           Select original audio for the active source
devices          List input/output devices and channel counts
setup audio      Guided LIVE setup: choose BlackHole input and physical output
source system    Select LIVE system audio (BlackHole 2ch)
source file      Return to the loaded-file player (stops LIVE)
input <name|id>  Select the standalone BlackHole 2ch input
output <name|id> Select speakers/headphones while audio is stopped
monitor start [44100|48000]  Start LIVE; default 48000 Hz
monitor stop     Stop LIVE and release the devices
status           Show source, mode, file/monitor state, timing, and output
window           Open the graphical controls for this session; close to return
help             Show these commands
exit             Stop audio, release resources, and return to the shell"""

HELP += "\nLaunch from the shell: isla window or python -m isla window (optional .[gui] extra)."


class TerminalController:
    def __init__(self, backend, preparation_factory=Preparation, live_backend=None, routing=None):
        self.player = BufferPlayer(backend)
        self.preparation_factory = preparation_factory
        self.job = None
        self.path = None
        self.closed = False
        self.source = "file"
        self.capture = "BlackHole 2ch"
        self.output = None
        self.live = LiveMonitor(live_backend if live_backend is not None else SystemCaptureBackend(backend, routing))
        self._setup_routing = routing
        self._setup_stage = None
        self._setup_inputs = []
        self._setup_outputs = []
        self._setup_input = None

    @property
    def setup_prompt(self):
        if self._setup_stage == "input":
            return "Select input (number/name or cancel): "
        if self._setup_stage == "output":
            return "Select output (number/name or cancel): "
        return "isla> "

    def _audio_setup_devices(self):
        """Offer only individually verified Core Audio devices; do not guess on failure."""
        from isla.coreaudio import CoreAudioRouting

        if self._setup_routing is None:
            self._setup_routing = CoreAudioRouting()
        native, _ = self._setup_routing.snapshot()
        portaudio = self.player.backend.devices()

        def unique_native(name, direction):
            found = [d for d in native if d["name"] == name and d["alive"] and d[direction]]
            return found[0] if len(found) == 1 else None

        captures = [d for d in portaudio if d["name"] == "BlackHole 2ch"
                    and d["max_input_channels"] == 2]
        blackhole = unique_native("BlackHole 2ch", "input")
        if len(captures) != 1 or blackhole is None or blackhole["transport"] != "virt":
            raise AudioError("Standalone BlackHole 2ch is missing or ambiguous. Check Audio MIDI Setup.")

        outputs = []
        for device in portaudio:
            if device["max_output_channels"] < 2 or device["name"] == "BlackHole 2ch":
                continue
            if sum(d["name"] == device["name"] for d in portaudio) != 1:
                continue
            native_device = unique_native(device["name"], "output")
            if native_device is not None and native_device["transport"] in CoreAudioRouting.PHYSICAL:
                outputs.append(device)
        if not outputs:
            raise AudioError("No verified physical stereo output found. Reconnect speakers/headphones and retry.")
        return captures, outputs

    @staticmethod
    def _audio_setup_menu(label, devices):
        return label + "\n" + "\n".join(f"  [{d['index']}] {d['name']}" for d in devices)

    def _cancel_audio_setup(self):
        self._setup_stage = None
        self._setup_inputs = []
        self._setup_outputs = []
        self._setup_input = None
        return "Audio setup canceled; previous routing preserved."

    def _begin_audio_setup(self):
        if self.live.running or self.player.stream is not None:
            raise ValueError("Stop LIVE monitoring or file playback before setup audio.")
        captures, outputs = self._audio_setup_devices()
        self._setup_inputs = captures
        self._setup_outputs = outputs
        self._setup_input = None
        self._setup_stage = "input"
        return ("ISLA — Audio Setup\n"
                "Select BlackHole 2ch for capture, then a physical stereo output.\n"
                "Type a listed number or exact name; type cancel to leave.\n"
                + self._audio_setup_menu("Available capture inputs:", captures))

    def _choose_audio_setup(self, line):
        value = " ".join(shlex.split(line)).strip()
        if value.casefold() == "cancel":
            return self._cancel_audio_setup()
        if value.casefold() == "help":
            return "Choose a listed number or exact device name, or type cancel."
        choices = self._setup_inputs if self._setup_stage == "input" else self._setup_outputs
        matches = [d for d in choices if value == str(d["index"]) or value.casefold() == d["name"].casefold()]
        if len(matches) != 1:
            return ("Not an eligible " + ("input" if self._setup_stage == "input" else "physical stereo output")
                    + ". Select a number/name shown below, or type cancel.\n"
                    + self._audio_setup_menu("Available devices:", choices))
        selected = matches[0]
        if self._setup_stage == "input":
            self._setup_input = selected
            self._setup_stage = "output"
            return (f"Capture selected: {selected['name']}\n"
                    + self._audio_setup_menu("Available physical stereo outputs:", self._setup_outputs))

        # Do not commit either selection until fresh devices have been validated.
        if self.live.running or self.player.stream is not None:
            self._cancel_audio_setup()
            raise ValueError("Audio started while configuring; setup canceled. Stop audio and retry.")
        try:
            fresh_inputs, fresh_outputs = self._audio_setup_devices()
            if not any(d["index"] == self._setup_input["index"] and d["name"] == self._setup_input["name"]
                       for d in fresh_inputs):
                raise AudioError("BlackHole device changed during setup. Retry.")
            if not any(d["index"] == selected["index"] and d["name"] == selected["name"]
                       for d in fresh_outputs):
                raise AudioError("Output device changed during setup. Retry.")
            # Only file playback state may be stopped; never start a live stream here.
            self.player.stop()
            self.output = self.player.backend.select_output(str(selected["index"]))
            self.capture = self._setup_input["name"]
            self.source = "system"
        except Exception:
            self._cancel_audio_setup()
            raise
        capture = self.capture
        output = self.output
        self._cancel_audio_setup()
        return (f"ISLA devices selected: capture from {capture} -> playback to {output}.\n"
                "macOS system audio routing is NOT changed or verified by setup audio.\n"
                f"NEXT: Open macOS System Settings > Sound > Output and choose {capture} "
                f"(NOT {output}). Keep {output} as the selected physical ISLA output.\n"
                "After changing macOS Sound, enter bypass, then monitor start to listen "
                "(or status to inspect).")

    def poll(self):
        self.player.refresh()
        if self.job is not None and not self.job.done:
            try:
                prepared = self.job.poll()
            except Exception:
                self.job.close()
                self.job = None
                raise
            if prepared:
                buffers, sr = prepared
                self.player.install(buffers, sr)
                self.path = self.job.path

    def execute(self, line):
        args = shlex.split(line)
        if not args:
            return ""
        command, *values = args
        command = command.lower()
        if (getattr(self, "_window_owner", None) is not None
                and getattr(self, "_window_thread", None) != threading.get_ident()):
            raise ValueError("The control window owns this session. Close it to return to terminal commands.")
        if command == "window" and not values:
            if self._setup_stage is not None:
                raise ValueError("Finish setup audio or type cancel before opening window.")
            from isla.window import run_window
            code = run_window(controller=self)
            return ("Control window closed; audio stopped. Terminal ready."
                    if code == 0 else "Control window unavailable; terminal session preserved.")
        if command == "exit" and not values:
            self.close()
            return "Audio stopped.\nResources released.\nGoodbye from ISLA."
        if self._setup_stage is not None:
            return self._choose_audio_setup(line)
        if command == "setup":
            if values != ["audio"]:
                raise ValueError("Usage: setup audio")
            return self._begin_audio_setup()
        # A pending/failed file preparation must not prevent stopping LIVE.
        if self.source == "file":
            self.poll()
        else:
            self.player.refresh()
        if command == "devices" and not values:
            devices = self.player.backend.devices()
            return "\n".join(f"{d['index']}: {d['name']} (input {d['max_input_channels']}, output {d['max_output_channels']}; default {d['default_samplerate']:g} Hz)" for d in devices) or "No audio devices available."
        if command == "source":
            if len(values) != 1 or values[0].lower() not in ("system", "file"):
                raise ValueError("Usage: source system|file")
            source = values[0].lower()
            if source == "system":
                self.player.stop()
            else:
                self.live.stop()
            self.source = source
            return "System audio selected. Use input/output, then monitor start." if source == "system" else "File source selected."
        if command in ("input", "output"):
            if not values:
                raise ValueError(f"Usage: {command} <exact device name|id>")
            if self.live.running or self.player.stream is not None:
                raise ValueError("Stop audio before changing devices.")
            selector = " ".join(values)
            if command == "input":
                device = self.player.backend.resolve_device(selector, "input")
                if device["name"] != "BlackHole 2ch":
                    raise ValueError("System capture requires standalone BlackHole 2ch.")
                self.capture = device["name"]
                return f"Capture selected: {self.capture}"
            self.output = self.player.backend.select_output(selector)
            return f"Output selected: {self.output}"
        if command == "monitor":
            if len(values) == 1 and values[0].lower() == "stop":
                return self.live.stop()
            if len(values) in (1, 2) and values[0].lower() == "start":
                if self.source != "system":
                    raise ValueError("Select source system before monitor start.")
                rate = 48000
                if len(values) == 2:
                    if values[1] not in ("44100", "48000"):
                        raise ValueError("Usage: monitor start [44100|48000]")
                    rate = int(values[1])
                return self.live.start(self.capture, self.output, rate)
            raise ValueError("Usage: monitor start [44100|48000] | monitor stop")
        if command == "load":
            if self.source != "file":
                raise ValueError("Use source file before loading a recording.")
            if not values:
                raise ValueError("Usage: load <path>")
            # Joining also accepts an unquoted pasted path containing spaces.
            job = self.preparation_factory(" ".join(values))
            try:
                self.player.close()
                if self.job is not None:
                    self.job.close()
            except BaseException:
                job.close()
                raise
            self.job = job
            self.path = None
            return "Loading audio and preparing Velvet, Legato, and Melt. Use status to check progress."
        if command == "mode":
            if len(values) != 1 or values[0].lower() not in MODES:
                raise ValueError("Usage: mode velvet|legato|melt")
            if self.source == "system":
                self.live.select(values[0].lower())
                return f"{self.live.mode.upper()} enabled (LIVE harmonic profile)."
            self._ready()
            self.player.select(values[0].lower())
            return f"{self.player.mode.upper()} enabled."
        if values:
            raise ValueError(f"Unexpected arguments for {command}. Type help for commands.")
        if command in ("play", "bypass"):
            if self.source == "system":
                if command == "play":
                    raise ValueError("Use monitor start for system audio.")
                self.live.select("bypass")
                return "Original system audio enabled."
            self._ready()
            if command == "play":
                return self.player.play()
            self.player.select("original")
            return "Original audio enabled."
        if command == "pause":
            if self.source == "system":
                raise ValueError("LIVE cannot pause the browser; use monitor stop.")
            return self.player.pause()
        if command == "stop":
            if self.source == "system":
                return self.live.stop()
            self.player.stop()
            return "Playback stopped."
        if command == "status":
            if self.source == "system":
                return (self.live.status() + f"\nSelected input: {self.capture}\nSelected output: {self.output or 'None'}")
            try:
                output = (self.player.output if self.player.stream is not None
                          else self.player.backend.output_name())
            except AudioError as exc:
                output = str(exc)
            player = self.player
            preparation = self.job.state if self.job else "No file loaded"
            duration = len(player.buffers["original"]) / player.sr if player.buffers else 0
            position = player.position / player.sr if player.sr else 0
            return (f"Source: File\nFile: {self.path or (self.job.path if self.job else 'None')}\n"
                    f"Preparation: {preparation}\nMode: {player.mode}\nStatus: {player.state}\n"
                    f"Position: {position:.2f} / {duration:.2f} s\nOutput: {output}"
                    + (f"\nWarning: {player.warning}" if player.warning else ""))
        if command == "help":
            return HELP
        raise ValueError(f"Unknown command: {command}. Type help for commands.")

    def _ready(self):
        if not self.player.buffers:
            if self.job is not None:
                raise ValueError(f"{self.job.state} Use status to check progress.")
            raise ValueError("Load an audio file first.")

    def close(self):
        try:
            self.live.stop()
        finally:
            try:
                self.player.close()
            finally:
                if self.job is not None:
                    self.job.close()
                    self.job = None
                self.closed = True
                self._cancel_audio_setup()


def run_terminal(input_fn=input, output_fn=print, backend=None, routing=None):
    try:
        controller = TerminalController(backend if backend is not None else SoundDeviceBackend(), routing=routing)
    except AudioError as exc:
        output_fn(f"Error: {exc}")
        return 1
    output_fn("ISLA — ALIVE + LIVE\nAudio Engine: Ready\nStatus: Idle\nType help for commands.")
    try:
        try:
            output_fn(f"Output: {controller.player.backend.output_name()}")
        except AudioError as exc:
            output_fn(f"Output unavailable: {exc}")
        while not controller.closed:
            try:
                line = input_fn(controller.setup_prompt)
            except KeyboardInterrupt:
                if controller._setup_stage is not None:
                    output_fn(controller._cancel_audio_setup())
                    continue
                output_fn(controller.execute("exit"))
                break
            except EOFError:
                output_fn(controller.execute("exit"))
                break
            try:
                result = controller.execute(line)
                if result:
                    output_fn(result)
            except (ValueError, RuntimeError, OSError) as exc:
                output_fn(f"Error: {exc}")
    finally:
        if not controller.closed:
            controller.close()
    return 0
