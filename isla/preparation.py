"""Cancellable file preparation in a separate process, away from audio output."""
from __future__ import annotations

import multiprocessing as mp
from pathlib import Path
import tempfile

import numpy as np
import soundfile as sf

MODES = ("velvet", "legato", "melt")


def _prepare(path, directory, connection):
    """Exchange small progress messages; large buffers live in mapped files."""
    try:
        from drivers.api import IslaBuffer

        audio, sr = sf.read(path, dtype="float32", always_2d=True)
        if not len(audio):
            raise ValueError("The recording is empty.")
        if audio.shape[1] not in (1, 2):
            raise ValueError("Only mono and stereo recordings are supported.")
        if not np.isfinite(audio).all():
            raise ValueError("The recording contains non-finite samples.")
        np.save(Path(directory) / "original.npy", audio)
        for mode in MODES:
            connection.send(("progress", f"Preparing {mode.upper()}..."))
            # The existing public API is the authoritative BEDROCK pipeline.
            result = IslaBuffer(mode=mode, sr=sr).process_buffer(audio)
            if result.shape != audio.shape or not np.isfinite(result).all():
                raise ValueError(f"{mode} returned invalid audio or changed its shape.")
            np.save(Path(directory) / f"{mode}.npy", np.asarray(result, dtype="float32"))
        connection.send(("ready", sr))
    except Exception as exc:
        connection.send(("error", str(exc)))
    finally:
        connection.close()


class Preparation:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise ValueError(f"Audio file not found: {self.path}")
        # Header check gives immediate, useful feedback without decoding the file.
        try:
            info = sf.info(str(self.path))
        except (RuntimeError, OSError) as exc:
            raise ValueError(f"Unsupported or invalid audio file: {self.path}") from exc
        if info.channels not in (1, 2) or not info.frames:
            raise ValueError("Load a non-empty mono or stereo recording.")
        self.directory = tempfile.TemporaryDirectory(prefix="isla-alive-")
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(target=_prepare, args=(str(self.path), self.directory.name, child), daemon=True)
        self.state = "Loading audio..."
        self.done = False
        try:
            self.process.start()
        except BaseException:
            self.connection.close()
            self.directory.cleanup()
            raise
        finally:
            child.close()

    def poll(self):
        if self.done:
            return None
        while self.connection.poll():
            try:
                kind, value = self.connection.recv()
            except EOFError:
                break
            if kind == "progress":
                self.state = value
            else:
                self.done = True
                if kind == "error":
                    raise ValueError(f"Could not prepare audio: {value}")
                buffers = {mode: np.load(Path(self.directory.name) / f"{mode}.npy", mmap_mode="r")
                           for mode in ("original", *MODES)}
                self.state = "Ready"
                return buffers, value
        if not self.process.is_alive():
            self.done = True
            raise ValueError("Audio preparation stopped unexpectedly; try a smaller recording.")
        return None

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join()
        self.process.close()
        self.connection.close()
        self.directory.cleanup()
