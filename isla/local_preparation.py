"""Apple audio adapter around the frozen ALIVE preparation/DSP pipeline."""
import multiprocessing as mp
import os
from pathlib import Path
import signal
import tempfile

from isla.audio_files import decode_apple_audio, inspect_audio
from isla.preparation import Preparation, _prepare


def _prepare_native(path, directory, connection):
    try:
        # The converter inherits this group, allowing Close to cancel it too.
        os.setsid()
        decoded = decode_apple_audio(path, directory)
        # Reuse the authoritative validation, DSP and publication unchanged.
        _prepare(str(decoded), directory, connection)
    except Exception as exc:
        connection.send(('error', str(exc)))
    finally:
        (Path(directory) / 'decoded.wav').unlink(missing_ok=True)
        connection.close()


class NativePreparation(Preparation):
    """Use the existing poll protocol, with a cancellable decoder before DSP."""
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.directory = tempfile.TemporaryDirectory(prefix='isla-alive-')
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(target=_prepare_native,
            args=(str(self.path), self.directory.name, child), daemon=True)
        self.state = 'Decoding local audio...'
        self.done = False
        try:
            self.process.start()
        except BaseException:
            self.connection.close()
            self.directory.cleanup()
            raise
        finally:
            child.close()

    def close(self):
        pid = self.process.pid
        if self.process.is_alive():
            self.process.terminate()
        self.process.join()
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        super().close()


def prepare_file(path):
    """Keep libsndfile inputs on their original path; adapt native Apple audio."""
    path = Path(path).expanduser().resolve()
    info = inspect_audio(path)
    return Preparation(path) if info is not None else NativePreparation(path)
