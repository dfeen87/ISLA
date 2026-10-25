"""Measure actual ALIVE/LIVE outgoing callbacks with deterministic memory devices.

python -m tools.control_acceptance_verify --output docs/control-center/final-volume-pcm.json
No hardware is opened. A scheduled dry DSP makes gain isolation reproducible;
actual prepared DSP comparisons are in audio_control_verify.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import threading
import time
from types import SimpleNamespace

import numpy as np

from isla.alive_listening_gain import AttenuatedALIVEBackend
from isla.live import BLOCK, WARMUP_BLOCKS, LiveConfig, LiveMonitor
from isla.monitor_gain import ListeningGainDSP, MonitorVolume
from isla.playback import BufferPlayer
from tools.audio_control_verify import MemoryBackend


class DuplexMemoryStream:
    def __init__(self, callback, rate):
        self.callback, self.rate = callback, rate
        self.active = self.closed = False
        self.clock = 100.
    def start(self): self.active = True
    def abort(self): self.active = False
    def close(self): self.closed = True
    def pump(self, data):
        out = np.empty_like(data)
        self.callback(data, out, BLOCK, SimpleNamespace(inputBufferAdcTime=self.clock,
                      outputBufferDacTime=self.clock+.01), None)
        self.clock += BLOCK/self.rate
        return out


class DuplexMemoryBackend:
    def __init__(self): self.streams = []
    def configure(self, capture, output, rate):
        return LiveConfig(0, 1, capture, output, rate, 2, (10, 11))
    def open(self, config, callback):
        stream = DuplexMemoryStream(callback, config.rate)
        self.streams.append(stream)
        return stream
    def validate(self, config): pass


def measure(actual, source, percent):
    expected = source * (percent/100)
    return dict(percent=percent, expected_multiplier=percent/100,
                measured_multiplier=float(np.sqrt(np.mean(actual.astype(float)**2)/
                                                   np.mean(source.astype(float)**2))),
                max_absolute_pcm_error=float(np.max(np.abs(actual-expected))),
                all_zero=not bool(np.any(actual)))


def verify(rate):
    x = np.full((BLOCK, 2), .4, np.float32)
    source_hash = hashlib.sha256(x.tobytes()).hexdigest()
    backend = MemoryBackend()
    adapter = AttenuatedALIVEBackend(backend)
    player = BufferPlayer(adapter)
    player.install({'original':np.tile(x, (32, 1))}, rate)
    player.play()
    alive, live, cursor = [], [], 0
    try:
        for percent in (0, 25, 50, 100):
            adapter.set_percent(percent)
            for _ in range(2):
                out = np.empty_like(x)
                backend.callback(out, BLOCK, SimpleNamespace(outputBufferDacTime=100+cursor/rate), False)
                cursor += BLOCK
            alive.append(measure(out, x, percent))
    finally:
        player.close()
    duplex, volume, gate = DuplexMemoryBackend(), MonitorVolume(50), threading.Event()
    gate.set()
    class ScheduledDry:
        delay = 0
        def __init__(self, *args): self.mode = 'bypass'
        def select(self, mode): self.mode = mode
        def process_block(self, block):
            if not gate.wait(5): raise RuntimeError('Verification scheduler timed out')
            return block.copy()
    monitor = LiveMonitor(duplex, processor_factory=lambda r,c: ListeningGainDSP(
        r,c,volume,delegate_factory=ScheduledDry), monotonic_clock=lambda:0.)
    monitor.start('Memory capture', 'Memory physical-output stand-in', rate)
    try:
        for _ in range(WARMUP_BLOCKS):
            monitor.stream.pump(np.zeros_like(x))
        for percent in (0, 25, 50, 100):
            volume.set_percent(percent)
            for _ in range(4):  # Settle ramp and bounded pipeline before measuring.
                gate.clear()
                try: out = monitor.stream.pump(x)
                finally: gate.set()
                deadline = time.monotonic()+5
                while monitor.output.count != 1 and not monitor.halt.is_set():
                    if time.monotonic()>deadline: raise RuntimeError('Output did not arrive')
                    time.sleep(.001)
                if monitor.halt.is_set(): raise RuntimeError(monitor.error)
            live.append(measure(out, x, percent))
        counters = dict(underflows=monitor.underflows, ring_failures=monitor.ring_failures)
    finally:
        gate.set()
        monitor.stop()
    assert all(row['max_absolute_pcm_error'] == 0 for row in alive+live)
    assert hashlib.sha256(x.tobytes()).hexdigest() == source_hash
    return dict(rate=rate, source_pcm_sha256=source_hash, alive=alive, live=live,
                alive_stream_restarts=0, live_stream_count=len(duplex.streams),
                live_counters=counters, capture_unchanged=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = dict(schema=1, scope='Outgoing memory-device callback PCM, not physical or acoustic output',
                  ramp_ms=5, cases=[verify(rate) for rate in (44100,48000)])
    with open(args.output, 'w') as f: json.dump(report, f, indent=2, allow_nan=False); f.write('\n')
    print('16 outgoing PCM gain cells PASS; capture unchanged; one LIVE stream per rate')


if __name__ == '__main__': main()
