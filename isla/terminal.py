"""ALIVE interactive terminal controller, independent of DAWs and services."""
from __future__ import annotations

import shlex

from isla.playback import AudioError, BufferPlayer, SoundDeviceBackend
from isla.preparation import MODES, Preparation

HELP = """load <path>      Load and prepare a local mono/stereo WAV (quote paths with spaces)
play             Start or resume playback
pause            Pause at the current position
stop             Stop and reset to the beginning
mode <name>      Select velvet, legato, or melt
bypass           Select the original recording
status           Show file, mode, playback state, position, and output
help             Show these commands
exit             Stop audio, release resources, and return to the shell"""


class TerminalController:
    def __init__(self, backend, preparation_factory=Preparation):
        self.player = BufferPlayer(backend)
        self.preparation_factory = preparation_factory
        self.job = None
        self.path = None
        self.closed = False

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
        self.poll()
        if command == "load":
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
            self._ready()
            self.player.select(values[0].lower())
            return f"{self.player.mode.upper()} enabled."
        if values:
            raise ValueError(f"Unexpected arguments for {command}. Type help for commands.")
        if command in ("play", "bypass"):
            self._ready()
            if command == "play":
                return self.player.play()
            self.player.select("original")
            return "Original audio enabled."
        if command == "pause":
            return self.player.pause()
        if command == "stop":
            self.player.stop()
            return "Playback stopped."
        if command == "status":
            try:
                output = (self.player.output if self.player.stream is not None
                          else self.player.backend.output_name())
            except AudioError as exc:
                output = str(exc)
            player = self.player
            preparation = self.job.state if self.job else "No file loaded"
            duration = len(player.buffers["original"]) / player.sr if player.buffers else 0
            position = player.position / player.sr if player.sr else 0
            return (f"File: {self.path or (self.job.path if self.job else 'None')}\n"
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
    output_fn("ISLA — ALIVE\nAudio Engine: Ready\nStatus: Idle\nType help for commands.")
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
