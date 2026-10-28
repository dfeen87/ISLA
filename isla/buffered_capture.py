"""Application capture defaults for a virtual input and physical listening sink.

The historical LIVE transport remains available unchanged. The application uses
robust native output buffering and capture pacing suited to the listening path;
callback size, bounded rings, routing validation and all LiveMonitor loss/recovery
checks are still shared.
"""
from isla.live import BLOCK, SystemCaptureBackend


def preferred_device_rate(device):
    """Match a supported output rate without changing a device property."""
    rate = device.get('default_samplerate')
    return int(rate) if rate in (44100, 48000) else 48000


def preferred_capture_rate(playback, output):
    if output is None:
        return 48000  # configure() supplies the missing-output guidance.
    return preferred_device_rate(playback.resolve_device(output, 'output'))


class BufferedSystemCaptureBackend(SystemCaptureBackend):
    """Keep robust output buffers without batching built-in capture callbacks."""

    def open(self, config, callback):
        native, _ = self.routing.snapshot()
        sink = next((device for device in native if device['id'] == config.identity[1]), None)
        # On the built-in output, high BlackHole capture latency causes
        # PortAudio to deliver eight 512-frame callbacks in one burst. That
        # exhausts the bounded output ring before its DSP worker can run.
        # Keep the physical output's robust buffering; Bluetooth retains the
        # verified high/high path needed for its separate device clocks.
        latency = ('low', 'high') if sink and sink['transport'] == 'bltn' else 'high'
        stream = self.playback.sd.Stream(
            device=(config.input_id, config.output_id), samplerate=config.rate,
            channels=(config.channels, config.channels), dtype='float32',
            blocksize=BLOCK, latency=latency, callback=callback,
        )
        try:
            self.routing.validate_stream(self.playback.sd, stream, config.identity)
            self.validate(config)
        except BaseException:
            stream.close()
            raise
        return stream
