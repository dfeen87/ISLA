"""Cancellable research render process; only a ready buffer reaches playback."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path
import tempfile

import numpy as np

from isla.remastered import RenderRequest, output_metrics, render_preview

# Frozen analysis materializes whole-file spectra. Bound admission, not its math.
MAX_SECONDS = 30


def _yield_priority_to_playback():
    """Best effort: give active audio more CPU opportunity than offline rendering."""
    try:
        os.nice(5)  # In the spawned child only; never change the parent/PortAudio priority.
    except (AttributeError, OSError):
        pass  # Platform lacks niceness or refuses the request; remain functional.


def _render(source, directory, sr, request, connection):
    try:
        _yield_priority_to_playback()
        connection.send(('progress', 'Loading the validated source…'))
        x = np.load(source, mmap_mode='r', allow_pickle=False)
        connection.send(('progress', f'Rendering {request.mode.title()} Remastered at '
                         f'{request.intensity}% depth in a separate process…'))
        y, report = render_preview(x, sr, request)
        connection.send(('stage', 'Validating'))
        connection.send(('progress', 'Checking numerical and output peak safeguards…'))
        buffer = np.asarray(y, dtype=np.float32)
        report['playback_output'] = output_metrics(x, buffer)
        report['numerical_pass'] = bool(report['numerical_pass'] and
            all(report['playback_output'][key] for key in ('finite', 'shape_preserved', 'peak_screen_pass')))
        # Retain measurements for rejected renders; never silently normalize.
        Path(directory, 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['numerical_pass']:
            raise ValueError('Render rejected by numerical/0.98 peak screens; active audio preserved. '
                             'Use a recording with more headroom. No limiter was applied.')
        connection.send(('progress', 'Saving verified audio for a safe mode change…'))
        np.save(Path(directory, 'rendered.npy'), buffer, allow_pickle=False)
        connection.send(('ready', None))
    except Exception as exc:
        connection.send(('error', str(exc)))
    finally:
        connection.close()


class RemasteredPreparation:
    def __init__(self, source, sr, request: RenderRequest):
        source = Path(source)
        x = np.load(source, mmap_mode='r', allow_pickle=False)
        if sr not in (44100, 48000):
            raise ValueError('Remastered supports 44.1/48 kHz; production playback is unchanged.')
        if x.ndim != 2 or x.shape[1] not in (1, 2) or not len(x):
            raise ValueError('Remastered needs non-empty mono or stereo audio.')
        if len(x) > sr * MAX_SECONDS:
            raise ValueError('Remastered preview supports excerpts up to 30 seconds; open a shorter recording.')
        self.directory = tempfile.TemporaryDirectory(prefix='isla-remastered-')
        context = mp.get_context('spawn')
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(target=_render,
            args=(str(source), self.directory.name, sr, request, child), daemon=True)
        self.done = self.closed = False
        self.state = 'Starting background Remastered preparation…'
        self.stage = 'Preparing'
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
            if kind == 'progress':
                self.state = value
                continue
            if kind == 'stage':
                self.stage = value
                continue
            self.done = True
            if kind == 'error':
                raise ValueError(value)
            if kind != 'ready':
                raise ValueError('Invalid Remastered worker response; active audio preserved.')
            # Copy away from the temporary mapping before publishing. Old
            # callback references remain ordinary owned arrays during crossfade.
            result = np.array(np.load(Path(self.directory.name, 'rendered.npy'),
                                      mmap_mode='r', allow_pickle=False), copy=True)
            report = json.loads(Path(self.directory.name, 'report.json').read_text())
            return result, report
        if not self.process.is_alive():
            self.done = True
            raise ValueError('Remastered render process stopped unexpectedly; active audio preserved.')
        return None

    def close(self):
        if self.closed:
            return
        if self.process.is_alive():
            self.process.terminate()
        self.process.join()
        self.process.close()
        self.connection.close()
        self.directory.cleanup()
        self.closed = True
