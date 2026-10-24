"""Reproducible PCM comparisons, never a physical-device listening verdict.

python -m tools.audio_control_verify --output docs/control-center/hardening-pcm.json
No hardware is opened. Timings describe this host, not a real-time guarantee.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

import numpy as np
from scipy.signal import hilbert
import soundfile as sf

from drivers.api import IslaBuffer
from isla.alive_listening_gain import AttenuatedALIVEBackend
from isla.playback import BufferPlayer
from isla.remastered import RenderRequest, render_preview


class MemoryBackend:
    class CallbackStop(Exception):
        pass

    def output_name(self):
        return 'Deterministic memory sink (no physical audio)'

    def open(self, samplerate, channels, callback, finished_callback):
        self.callback, self.finished = callback, finished_callback
        return SimpleNamespace(active=True, start=lambda: None, abort=lambda: None,
                               close=lambda: None, time=100.)


def transport(buffers, sr):
    backend = MemoryBackend()
    adapter = AttenuatedALIVEBackend(backend)
    player = BufferPlayer(adapter)
    player.install(buffers, sr)
    player.play()
    counts, errors, timings = {}, {}, []
    try:
        for index, mode in enumerate(buffers):
            start, previous = player.cursor, player._selected
            player.select(mode)
            out = np.empty((512, buffers[mode].shape[1]), np.float32)
            before = time.perf_counter()
            backend.callback(out, 512, SimpleNamespace(outputBufferDacTime=100+start/sr), False)
            timings.append((time.perf_counter()-before)*1000)
            expected = buffers[mode][start:start+512].copy()
            if index:
                n = len(player._fade)
                expected[:n] = (expected[:n]*player._fade +
                                previous[start:start+n]*player._inverse)
            expected *= .25
            errors[mode] = float(np.max(np.abs(out-expected)))
            counts[mode] = player.cursor - start
        return dict(callback_pcm_max_error=errors, consumed_frames=counts,
                    callback_max_ms=max(timings), block_budget_ms=512/sr*1000,
                    counters=adapter.diagnostics(), stream_restarts=0)
    finally:
        player.close()


def uninterrupted_transport(buffer, sr):
    backend = MemoryBackend()
    adapter = AttenuatedALIVEBackend(backend)
    player = BufferPlayer(adapter)
    player.install({'original':buffer}, sr)
    player.play()
    chunks, timings = [], []
    try:
        while player.cursor < len(buffer):
            start = player.cursor
            out = np.empty((512,buffer.shape[1]),np.float32)
            before = time.perf_counter()
            try:
                backend.callback(out,512,SimpleNamespace(outputBufferDacTime=100+start/sr),False)
            except backend.CallbackStop:
                pass
            timings.append((time.perf_counter()-before)*1000)
            chunks.append(out)
        rendered = np.concatenate(chunks)
        error = float(np.max(np.abs(rendered[:len(buffer)]-buffer*.25)))
        return dict(outgoing_pcm_max_error=error, tail_nonzero=int(np.count_nonzero(rendered[len(buffer):])),
                    callback_max_ms=max(timings), counters=adapter.diagnostics())
    finally:
        player.close()


def measures(x, y, sr):
    x, y = x.astype(float), y.astype(float)
    trim = min(round(sr*.2), len(x)//4)
    core = y[trim:-trim, 0]
    envelope = np.abs(hilbert(core))
    scalar = float(np.sum(x*y)/np.sum(x*x)) if np.any(x) else 0
    return dict(peak=float(np.max(np.abs(y))),
                relative_residual_rms=float(np.sqrt(np.mean((y-x)**2)/np.mean(x*x))),
                fitted_gain=scalar,
                gain_matched_residual_rms=float(np.sqrt(np.mean((y-scalar*x)**2)/np.mean(x*x))),
                max_adjacent_step=float(np.max(np.abs(np.diff(y, axis=0)))),
                adjacent_steps_over_005=int(np.count_nonzero(np.abs(np.diff(y, axis=0))>.05)),
                residual_steps_over_002=int(np.count_nonzero(np.abs(np.diff(y-x, axis=0))>.02)),
                envelope_p05=float(np.percentile(envelope,5)),
                envelope_p95=float(np.percentile(envelope,95)),
                envelope_cv=float(np.std(envelope)/np.mean(envelope)),
                finite=bool(np.isfinite(y).all()))


def verify():
    cases = []
    for sr in (44100, 48000):
        t = np.arange(3*sr)/sr
        tone = (.25*np.sin(2*np.pi*997*t)).astype(np.float32)
        cases.append((f'sustained_997Hz_{sr}', tone[:,None], sr))
        envelope = sum(np.exp(-np.maximum(t-start,0)*5)*(t>=start) for start in (.15,.8,1.5,2.2))
        melody = (envelope*(.12*np.sin(2*np.pi*220*t)+.06*np.sin(2*np.pi*330*t))).astype(np.float32)
        cases.append((f'attacks_and_decays_{sr}', np.column_stack((melody,melody)), sr))
    root = Path(__file__).resolve().parents[1]
    for track in ('ember', 'outbreaker'):
        x, sr = sf.read(root/f'docs/audio/electronic-comparison/{track}/original.flac',
                        dtype='float32', always_2d=True)
        cases.append((track+'_preserved_excerpt_first_3s',x[:3*sr],sr))
    report = dict(schema=1, scope='Offline float32 PCM and manually pumped callback; no native audio',
                  thresholds='Step counts are descriptive, not audibility or scientific acceptance gates.',
                  sources=[])
    for name, x, sr in cases:
        result = dict(name=name, rate=sr, channels=x.shape[1], samples=len(x),
                      source_pcm_sha256=hashlib.sha256(x.tobytes()).hexdigest(), modes={})
        buffers = {'original':x}
        if name.startswith('sustained'):
            engine = IslaBuffer('melt',sr).engine
            boundaries = engine.analyzer.detect_boundaries(x,sr)
            result['ablation'] = dict(boundary_count=len(boundaries),
                first_boundary_seconds=[b/sr for b in boundaries[:8]],
                smoother_only=measures(x,engine.smoother.apply(x,boundaries,sr),sr),
                harmonic_only=measures(x,engine.harmonics.blend(x,sr),sr))
        result['modes']['original'] = measures(x,x,sr)
        for mode in ('velvet','legato','melt'):
            before = time.perf_counter()
            y = np.asarray(IslaBuffer(mode,sr).process_buffer(x),dtype=np.float32)
            result['modes'][mode] = dict(measures(x,y,sr),render_seconds=time.perf_counter()-before)
            buffers[mode] = y
            for intensity in (0,100):
                before = time.perf_counter()
                remastered, validation = render_preview(x,sr,RenderRequest(mode,intensity))
                remastered = remastered.astype(np.float32)
                result['modes'][f'remastered_{mode}_{intensity}'] = dict(
                    measures(x,remastered,sr),numerical_pass=validation['numerical_pass'],
                    render_seconds=time.perf_counter()-before)
        result['mode_switch_transport'] = transport(buffers,sr)
        result['uninterrupted_transport'] = {mode:uninterrupted_transport(y,sr) for mode,y in buffers.items()}
        report['sources'].append(result)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = verify()
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(f'Wrote {len(result["sources"])} identical-passage comparisons to {args.output}')


if __name__ == '__main__':
    main()
