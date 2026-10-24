"""Creator-run scalar LIVE reliability record; never changes macOS routing.

Configure the single BlackHole -> physical output path manually first.
No captured audio is saved. A completed observation is not listening acceptance.
"""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time

from isla.live import LiveMonitor, SystemCaptureBackend
from isla.playback import SoundDeviceBackend
from isla.streaming import MODES

COUNTERS = ("input_overflows", "input_underflows", "output_underflows", "output_overflows",
            "device_status", "underflows", "overflows", "ring_failures", "nonfinite",
            "capture_discontinuities", "recovery_attempts", "recoveries", "failed_recoveries",
            "fatal_device_errors", "discarded_blocks", "concealed_blocks")


def snapshot(monitor):
    return dict(state=monitor.state, mode=monitor.mode, error=monitor.error,
                recovery_state=monitor.recovery_state, last_interruption=monitor.last_interruption,
                counters={key: getattr(monitor, key) for key in COUNTERS},
                latency_ms=monitor.latency_ms, max_queue_age_ms=monitor.max_queue_age_ms,
                max_worker_ms=monitor.max_worker_ms, max_routing_ms=monitor.max_routing_ms,
                input_rms=monitor.input_rms, output_rms=monitor.output_rms)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Exact selected physical output name")
    parser.add_argument("--mode", choices=MODES, default="bypass")
    parser.add_argument("--rate", type=int, choices=(44100, 48000), default=48000)
    parser.add_argument("--seconds", type=int, default=1800, help="Observation length, 1..14400 seconds")
    parser.add_argument("--status-every", type=int, default=30, help="Periodic status interval, 1..300 seconds")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 14400 or not 1 <= args.status_every <= 300:
        parser.error("Use --seconds 1..14400 and --status-every 1..300")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1], text=True, timeout=3).strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unavailable"
    def emit(event, **values):
        print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), event=event, **values)), flush=True)
    playback = SoundDeviceBackend()
    monitor = LiveMonitor(SystemCaptureBackend(playback))
    monitor.select(args.mode)
    emit("environment", commit=commit, version=version("isla-audio"),
         platform=platform.platform(), python=platform.python_version(),
         sounddevice=playback.sd.__version__, portaudio=playback.sd.get_portaudio_version(),
         capture="BlackHole 2ch", output=args.output, rate=args.rate, seconds=args.seconds,
         note="Scalar observations only; no saved audio or automatic routing changes")
    result = 0
    try:
        monitor.start("BlackHole 2ch", args.output, args.rate)
        emit("started", stream_latency_seconds=monitor.stream.latency, **snapshot(monitor))
        started = last_report = time.monotonic()
        previous = None
        while time.monotonic() - started < args.seconds:
            current = snapshot(monitor)
            signature = (current["state"], current["recovery_state"], tuple(current["counters"].values()))
            now = time.monotonic()
            if signature != previous or now - last_report >= args.status_every:
                emit("status", elapsed_seconds=now - started, **current)
                previous, last_report = signature, now
            if not monitor.running:
                result = 1
                break
            time.sleep(.2)
    except KeyboardInterrupt:
        result = 130
    except Exception as exc:
        emit("exception", message=str(exc))
        result = 1
    finally:
        try:
            monitor.stop()
        finally:
            emit("stopped", exit_code=result, **snapshot(monitor))
            emit("operator_action", message="Restore your normal physical output in macOS Sound settings after LIVE.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
