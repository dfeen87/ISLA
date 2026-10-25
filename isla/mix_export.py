"""Lossless ALIVE mix export, independent of listening output and frozen DSP.

Write the currently selected, already-prepared PCM to a new 32-bit float WAV.
The export worker never opens an audio device, modifies DSP buffers, or applies
the Control Center's 25% listening-only safety attenuation.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import time

import numpy as np
import soundfile as sf


class MixExport:
    """One cancelable background WAV export; output is published atomically."""

    CHUNK_FRAMES = 65536

    def __init__(self):
        self.pending = False
        self.status = 'No mix saved yet.'
        self.mode = ''
        self.saved_path = ''
        self._cancel = threading.Event()
        self._thread = None

    def start(self, samples, rate, mode, destination):
        if self.pending:
            raise ValueError('A mix is already being saved. Cancel or finish it first.')
        target = Path(destination).expanduser()
        if target.suffix.lower() != '.wav':
            raise ValueError('Save Mix supports only .wav (32-bit float).')
        if not target.parent.is_dir():
            raise ValueError('Choose an existing, writable destination folder.')
        if target.exists() or target.is_symlink():
            raise FileExistsError(f'File already exists; choose another name: {target}')
        if (not isinstance(samples, np.ndarray) or samples.dtype != np.float32
                or samples.ndim != 2 or samples.shape[1] not in (1, 2)
                or not len(samples) or not isinstance(rate, int) or rate <= 0):
            raise ValueError('No valid prepared mono/stereo float32 ALIVE audio to save.')
        self.mode = mode
        self.saved_path = ''
        self.status = f'Saving {mode} mix as lossless 32-bit float WAV…'
        self._cancel = threading.Event()
        self.pending = True
        self._thread = threading.Thread(
            target=self._write, args=(samples, rate, target, self._cancel),
            name='isla-mix-export', daemon=False,
        )
        try:
            self._thread.start()
        except BaseException:
            self.pending = False
            self.status = 'Unable to start the save worker; nothing was written.'
            raise
        return self.status

    def _write(self, samples, rate, target, cancellation):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix='.isla-mix-', suffix='.partial', dir=target.parent, delete=False
            ) as staged:
                temporary = Path(staged.name)
            with sf.SoundFile(str(temporary), mode='w', samplerate=rate,
                              channels=samples.shape[1], format='WAV',
                              subtype='FLOAT') as output:
                for start in range(0, len(samples), self.CHUNK_FRAMES):
                    if cancellation.is_set():
                        self.status = 'Mix save canceled; no destination file created.'
                        return
                    block = samples[start:start + self.CHUNK_FRAMES]
                    if not np.isfinite(block).all():
                        raise ValueError('Export rejected nonfinite prepared samples.')
                    output.write(block)
                    # Yield to real-time audio; saving cannot take precedence.
                    time.sleep(0.001)
                output.flush()
            if cancellation.is_set():
                self.status = 'Mix save canceled; no destination file created.'
                return
            # Same-directory hard link is an atomic, no-overwrite publication:
            # it fails rather than replacing an existing recording.
            os.link(str(temporary), str(target))
            self.saved_path = str(target)
            self.status = f'Saved {self.mode} mix: {target}'
        except Exception as exc:
            self.status = f'Mix save failed; original preserved: {exc}'
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            self.pending = False

    def cancel(self):
        if not self.pending:
            return 'No mix save is running.'
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                raise RuntimeError('Mix save is still stopping; keep the window open.')
        return self.status
