"""Optional bounded native signal probe; no routing changes or saved audio.

Manually configure the README single listening path, play browser piano, then:
  python tools/live_native_probe.py --output 'External Headphones' --rate 44100
This prints scalar comparisons, not owner listening or acoustic acceptance.
"""
import argparse
import json
import platform
import time

import numpy as np

from isla.live import LiveMonitor, SystemCaptureBackend
from isla.playback import SoundDeviceBackend
from isla.streaming import StreamingDSP


class SignalProbe(StreamingDSP):
    def __init__(self, rate, channels):
        super().__init__(rate, channels)
        self.reference = np.zeros((self.delay, channels), np.float32)
        self.metrics = {}
        self.previous = None
        self.settle = 0

    def process_block(self, block):
        dry = self.reference[:self.hop].copy()
        self.reference[:-self.hop] = self.reference[self.hop:]
        self.reference[-self.hop:] = block
        result = super().process_block(block)
        if self.mode != self.previous:
            self.previous, self.settle = self.mode, 10
        if self.settle:
            self.settle -= 1
            return result
        metric = self.metrics.setdefault(self.mode, dict(samples=0, dry_energy=0., error_energy=0., peak_error=0.))
        error = result.astype(float) - dry
        metric["samples"] += result.size
        metric["dry_energy"] += float(np.sum(dry.astype(float) ** 2))
        metric["error_energy"] += float(np.sum(error ** 2))
        metric["peak_error"] = max(metric["peak_error"], float(np.max(np.abs(error))))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rate", type=int, choices=(44100, 48000), default=48000)
    parser.add_argument("--seconds", type=int, choices=range(1, 61), default=10, metavar="1..60")
    args = parser.parse_args()
    monitor = LiveMonitor(SystemCaptureBackend(SoundDeviceBackend()), SignalProbe)
    try:
        monitor.start("BlackHole 2ch", args.output, args.rate)
        for mode in ("bypass", "velvet", "legato", "melt", "bypass"):
            monitor.select(mode)
            print(f"Listening: {mode}", flush=True)
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                if not monitor.running:
                    raise RuntimeError(monitor.error or "Monitor stopped unexpectedly")
                time.sleep(.05)
            print(monitor.status(), flush=True)
    finally:
        monitor.stop()
        if hasattr(monitor, "processor"):
            print(json.dumps(dict(macos=platform.mac_ver()[0], rate=args.rate,
                output=args.output, error=monitor.error, underflows=monitor.underflows,
                overflows=monitor.overflows, device_status=monitor.device_status,
                latency_ms=monitor.latency_ms, modes=monitor.processor.metrics), indent=2))
        print("Stopped. Restore your physical output in macOS Sound settings.")


if __name__ == "__main__":
    main()
