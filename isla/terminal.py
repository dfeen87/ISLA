"""ALIVE interactive terminal controller, independent of DAWs and services."""
from __future__ import annotations

import shlex
import threading

from isla.playback import AudioError, BufferPlayer, SoundDeviceBackend
from isla.preparation import MODES
from isla.local_preparation import prepare_file
from isla.live import LiveMonitor, SystemCaptureBackend

from isla.terminal_help import mode_name, next_step, render_help
from isla.file_search import is_bare_filename
from isla.search_preparation import SearchPreparation
from isla.live_engine import LiveEngineFactory, LiveSettings, current_engine
from isla.device_refresh import eligible_devices, refresh_portaudio


class TerminalController:
    def __init__(self, backend, preparation_factory=prepare_file, live_backend=None, routing=None):
        self.player = BufferPlayer(backend)
        self.preparation_factory = preparation_factory
        self.job = None
        self.path = None
        self.closed = False
        self.source = "file"
        self.capture = "BlackHole 2ch"
        self.output = None
        self.live_settings = LiveSettings()
        self.live = LiveMonitor(live_backend if live_backend is not None else SystemCaptureBackend(backend, routing),
                                processor_factory=LiveEngineFactory(self.live_settings))
        self._setup_routing = routing
        self._setup_stage = None
        self._setup_inputs = []
        self._setup_outputs = []
        self._setup_input = None
        self._setup_single = False

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
        refresh_portaudio(self)
        native, _ = self._setup_routing.snapshot()
        portaudio = self.player.backend.devices()
        captures,outputs = eligible_devices(native,portaudio)
        if len(captures) != 1:
            raise AudioError("Standalone BlackHole 2ch is missing or ambiguous. Check Audio MIDI Setup.")
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
        self._setup_single = False
        return "Audio setup canceled; previous routing preserved."

    def _begin_audio_setup(self):
        if self.live.running or self.player.stream is not None:
            raise ValueError("Stop LIVE monitoring or file playback before setup audio.")
        captures, outputs = self._audio_setup_devices()
        self._setup_inputs = captures
        self._setup_outputs = outputs
        self._setup_input = None
        self._setup_single = False
        self._setup_stage = "input"
        return ("ISLA — Audio Setup\n"
                "Select BlackHole 2ch for capture, then a physical stereo output.\n"
                "Type a listed number or exact name; type cancel to leave.\n"
                + self._audio_setup_menu("Available capture inputs:", captures))

    def _begin_device_picker(self, direction):
        """Select one verified device from a number-only terminal prompt."""
        if self.source != "system":
            raise ValueError("Select source system first; file playback still accepts output <name|id>.")
        self._require_device_idle(direction)
        captures, outputs = self._audio_setup_devices()
        self._setup_inputs, self._setup_outputs = captures, outputs
        self._setup_input = None
        self._setup_single = True
        self._setup_stage = direction
        choices = captures if direction == "input" else outputs
        label = "Available BlackHole capture inputs:" if direction == "input" else "Available physical stereo outputs:"
        return ("Choose a listed number (or exact name), or type cancel.\n"
                + self._audio_setup_menu(label, choices))

    def _require_device_idle(self, direction):
        if self.live.running or self.live.stream is not None:
            raise ValueError(
                f"Cannot change audio {direction} while LIVE is running or stopping.\n"
                f"1. Type monitor stop.\n2. Type {direction}.\n"
                "3. Choose a listed " + ("physical stereo output" if direction == "output" else "BlackHole capture input")
                + " by number.\n4. Recheck macOS routing if required.\n5. Type monitor start.\n"
                f"Your active {direction} has not been changed.")
        if self.player.stream is not None:
            raise ValueError("Stop audio before changing devices. ALIVE: type stop, then retry " + direction + ".")

    @staticmethod
    def _same_device(left, right):
        return (left["index"], left["name"], left["native_id"]) == (
            right["index"], right["name"], right["native_id"])

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
        if self._setup_single:
            # Revalidate PortAudio index, CoreAudio identity and eligibility.
            if self.live.running or self.player.stream is not None:
                self._cancel_audio_setup()
                raise ValueError("Audio started during selection. Stop audio and retry.")
            try:
                fresh_inputs, fresh_outputs = self._audio_setup_devices()
                fresh = fresh_inputs if self._setup_stage == "input" else fresh_outputs
                if not any(self._same_device(selected, d) for d in fresh):
                    raise AudioError("Device changed during selection. Type input/output to refresh.")
                if self._setup_stage == "input":
                    self.capture = selected["name"]
                    message = f"Capture selected: {self.capture}"
                else:
                    self.output = self.player.backend.select_output(str(selected["index"]))
                    message = f"Output selected: {self.output}"
            finally:
                self._cancel_audio_setup()
            return message
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
            if not any(self._same_device(d, self._setup_input) for d in fresh_inputs):
                raise AudioError("BlackHole device changed during setup. Retry.")
            if not any(self._same_device(d, selected) for d in fresh_outputs):
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
        if command in ("help", "?"):
            if len(values) > 1:
                return "Usage: help [live|file|devices|modes|troubleshoot] (or ?)."
            return render_help(self, values[0] if values else "")
        # Cleanup must remain available even during a device picker or failed
        # file preparation. Neither command starts or reconfigures audio.
        if command == "monitor" and [v.lower() for v in values] == ["stop"]:
            return self.live.stop() + "\nNEXT: " + next_step(self)
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
            return "System audio selected. Type input/output for numbered menus, then monitor start." if source == "system" else "File source selected."
        if command in ("input", "output"):
            if not values:
                return self._begin_device_picker(command)
            self._require_device_idle(command)
            selector = " ".join(values)
            if self.source == "system" and command == "output":
                # Direct legacy commands remain usable without a native
                # CoreAudio scan. The actual LIVE start still verifies routing
                # and identities; guided pickers use stronger native filtering.
                try:
                    candidate = self.player.backend.resolve_device(selector, "output")
                except AudioError as exc:
                    raise ValueError(
                        f"Not an eligible physical stereo output: {selector}. "
                        "Type output to list verified numbers.") from exc
                if (candidate["max_output_channels"] < 2
                        or candidate["name"] == "BlackHole 2ch"
                        or "aggregate" in candidate["name"].casefold()
                        or "multi-output" in candidate["name"].casefold()):
                    raise ValueError(
                        f"Not an eligible physical stereo output: {selector}. "
                        "Type output to list verified numbers.")
                selector = str(candidate["index"])
            if command == "input":
                device = self.player.backend.resolve_device(selector, "input")
                if device["name"] != "BlackHole 2ch":
                    raise ValueError("System capture requires standalone BlackHole 2ch.")
                self.capture = device["name"]
                return f"Capture selected: {self.capture}"
            self.output = self.player.backend.select_output(selector)
            return f"Output selected: {self.output}"
        if command == 'engine':
            if self.source != 'system':
                raise ValueError('LIVE engine selection requires source system.')
            if len(values) not in (1,2):
                raise ValueError('Usage: engine production|remastered [0–100 in 5% steps]')
            engine = current_engine(getattr(self.live,'processor',None))
            if self.live.running and engine is None:
                raise ValueError('Stop and restart LIVE with the standard engine before changing processing.')
            try:
                intensity = int(values[1]) if len(values) == 2 else self.live_settings.request.intensity
            except ValueError as exc:
                raise ValueError('Intensity must be an integer, 0–100 in 5% steps.') from exc
            self.live_settings.set(values[0].lower(),intensity)
            return f'LIVE engine requested: {values[0].title()}, {intensity}% permitted Remastered depth.'
        if command == "monitor":
            if len(values) in (1, 2) and values[0].lower() == "start":
                if self.source != "system":
                    raise ValueError("Select source system before monitor start.")
                rate = 48000
                if len(values) == 2:
                    if values[1] not in ("44100", "48000"):
                        raise ValueError("Usage: monitor start [44100|48000]")
                    rate = int(values[1])
                if self.live.running and not self.live.halt.is_set():
                    return ("LIVE monitoring is already active. Current mode: " + mode_name(self.live.mode)
                            + ".\nNEXT: Choose mode velvet, mode legato, mode melt, or bypass. "
                            "Use monitor stop before changing devices.")
                if getattr(self,'_window_owner',None) is None:
                    refresh_portaudio(self)
                return self.live.start(self.capture, self.output, rate) + "\nNEXT: " + next_step(self)
            raise ValueError("Usage: monitor start [44100|48000] | monitor stop")
        if command == "load":
            if self.source != "file":
                raise ValueError("Use source file before loading a recording.")
            if not values:
                raise ValueError("Usage: load <path>")
            # Joining also accepts an unquoted pasted path containing spaces.
            requested = " ".join(values)
            try:
                job = self.preparation_factory(requested)
            except ValueError as exc:
                # Only a missing bare filename initiates discovery. Explicit
                # paths and invalid/unsupported audio retain their exact errors.
                if not is_bare_filename(requested) or not str(exc).startswith('Audio file not found:'):
                    raise
                job = SearchPreparation(requested,self.preparation_factory)
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
                return f"{self.live.mode.upper()} selected (LIVE harmonic profile; applied on the next processed block).\nNEXT: " + next_step(self)
            self._ready()
            self.player.select(values[0].lower())
            return f"{self.player.mode.upper()} enabled."
        if values:
            raise ValueError(f"Unexpected arguments for {command}. Type help for commands.")
        if command in ("play", "bypass"):
            if self.source == "system":
                if command == "play":
                    if self.live.running:
                        return ("LIVE monitoring is already running; system audio is being captured. "
                                "The 'play' command is for local audio files.\nNEXT: " + next_step(self))
                    raise ValueError("play is for ALIVE local audio files. LIVE uses monitor start.\nNEXT: " + next_step(self))
                self.live.select("bypass")
                return ("Original system audio enabled (Bypass / unprocessed input). "
                        + ("LIVE monitoring remains running in the existing stream." if self.live.running else
                           "LIVE remains stopped; use monitor start when ready."))
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
                engine = current_engine(getattr(self.live,'processor',None))
                return (self.live.status() + f"\nSelected input: {self.capture}\nSelected output: {self.output or 'None'}"
                        + f"\nRequested LIVE engine: {self.live_settings.request.engine}, {self.live_settings.request.intensity}% permitted depth"
                        + ('\n'+engine.diagnostics if engine is not None else '') + '\nNEXT: ' + next_step(self))
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
