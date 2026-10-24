"""ALIVE interactive terminal controller, independent of DAWs and services."""
from __future__ import annotations

import shlex

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
source system    Select LIVE system audio (BlackHole 2ch)
source file      Return to the loaded-file player (stops LIVE)
input <name|id>  Select the standalone BlackHole 2ch input
output <name|id> Select speakers/headphones while audio is stopped
monitor start [44100|48000]  Start LIVE; default 48000 Hz
monitor stop     Stop LIVE and release the devices
status           Show source, mode, file/monitor state, timing, and output
help             Show these commands
exit             Stop audio, release resources, and return to the shell"""


class TerminalController:
    def __init__(self, backend, preparation_factory=Preparation, live_backend=None):
        self.player = BufferPlayer(backend)
        self.preparation_factory = preparation_factory
        self.job = None
        self.path = None
        self.closed = False
        self.source = "file"
        self.capture = "BlackHole 2ch"
        self.output = None
        self.live = LiveMonitor(live_backend if live_backend is not None else SystemCaptureBackend(backend))

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
        if command == "exit" and not values:
            self.close()
            return "Audio stopped.\nResources released.\nGoodbye from ISLA."
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


def run_terminal(input_fn=input, output_fn=print, backend=None):
    try:
        controller = TerminalController(backend if backend is not None else SoundDeviceBackend())
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
                line = input_fn("isla> ")
            except (EOFError, KeyboardInterrupt):
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
