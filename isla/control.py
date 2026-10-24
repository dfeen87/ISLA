"""Toolkit-independent window coordination over the existing terminal session.

Only the window command worker calls this service. It never creates a second
player/monitor. Device choices retain native identities as well as names/indices;
readiness is advisory and start performs a fresh preflight before LiveMonitor's
own configure/open/worker validation. No system routing property is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import shlex
import threading

from isla.playback import AudioError
from isla.monitor_gain import ListeningGainDSP, MonitorVolume
from isla.streaming import StreamingDSP


class UIState(str, Enum):
    NO_FILE = "No file loaded"
    PREPARING = "File preparation in progress"
    READY = "File ready"
    PLAYING = "File playing"
    PAUSED = "File paused"
    STOPPED = "File stopped"
    LIVE_UNCONFIGURED = "LIVE setup required"
    LIVE_SOURCE = "LIVE source selected"
    LIVE_DEVICES = "LIVE devices selected"
    ROUTING_INVALID = "Routing invalid / action required"
    LIVE_READY = "LIVE ready"
    LIVE_RUNNING = "LIVE running"
    LIVE_STOPPING = "LIVE stopping"
    RECOVERABLE_ERROR = "Recoverable error"
    FATAL_ERROR = "Fatal audio failure"


@dataclass(frozen=True)
class DeviceChoice:
    index: int
    name: str
    native_id: int


@dataclass(frozen=True)
class ControlState:
    file_state: UIState
    live_state: UIState
    file_name: str
    preparation: str
    position: float
    duration: float
    file_mode: str
    live_mode: str
    source: str
    capture: str
    output: str
    system_output: str
    captures: tuple[DeviceChoice, ...]
    outputs: tuple[DeviceChoice, ...]
    selected_capture: DeviceChoice | None
    selected_output: DeviceChoice | None
    rate: int
    routing_ready: bool
    routing_message: str
    error: str
    file_warning: str
    live_health: str
    stream_active: bool
    live_active: bool
    can_play: bool
    can_prepare: bool
    can_configure: bool
    can_start: bool
    closed: bool
    live_applied_mode: str | None
    monitor_volume: int
    live_failure_reason: str


class ControlService:
    """Exclusive, serialized UI lease; the terminal is suspended during use."""
    def __init__(self, controller, *, owns_controller=False):
        if controller.closed:
            raise AudioError("This session is closed; launch isla window from the shell.")
        if getattr(controller, "_window_owner", None) is not None:
            raise AudioError("A control window already owns this audio session.")
        if controller._setup_stage is not None:
            raise AudioError("Finish setup audio or type cancel before opening window.")
        self.controller = controller
        self.owns_controller = owns_controller
        self.closed = False
        self.error = ""
        self.routing_message = "Select LIVE devices, then recheck audio routing."
        self.system_output = "Not checked"
        self.captures = self.outputs = ()
        self.selected_capture = self.selected_output = None
        self.rate = controller.live.config.rate if controller.live.config else 48000
        self.ready = False
        self._initial_devices = True
        self._file_touched = controller.player.state != 'stopped'
        if controller._setup_routing is None:
            controller._setup_routing = getattr(controller.live.backend, 'routing', None)
        # The optional listening attenuation is a separate adapter. Never
        # change the byte-frozen LiveMonitor or StreamingDSP implementation.
        self._original_live_factory = controller.live.processor_factory
        self._monitor_volume = MonitorVolume()
        factory = self._original_live_factory or StreamingDSP
        controller.live.processor_factory = (
            lambda rate, channels: ListeningGainDSP(
                rate, channels, self._monitor_volume, delegate_factory=factory))
        controller._window_owner = self

    def _enter(self):
        if self.closed or self.controller._window_owner is not self:
            raise AudioError("The control window no longer owns this session.")
        # Bound once: even accidental cross-thread calls cannot race backend state.
        ident = threading.get_ident()
        if getattr(self.controller, "_window_thread", None) not in (None, ident):
            raise AudioError("Audio commands must run on the owning window worker.")
        self.controller._window_thread = ident

    def _idle(self):
        c = self.controller
        if c.player.stream is not None or c.live.running or c.live.stream is not None:
            raise AudioError("Stop ALIVE and LIVE before changing source or devices.")

    def refresh_devices(self):
        self._enter()
        c = self.controller
        self.ready = False
        self.captures = self.outputs = ()
        try:
            if c._setup_routing is None:
                from isla.coreaudio import CoreAudioRouting
                c._setup_routing = CoreAudioRouting()
            routing = c._setup_routing
            if hasattr(c.live.backend, 'routing') and c.live.backend.routing is None:
                c.live.backend.routing = routing
            native, default = routing.snapshot()
            self.system_output = next((d['name'] for d in native if d['id'] == default), "Unknown device")
            captures, outputs = c._audio_setup_devices()
            def choices(devices, direction):
                return tuple(DeviceChoice(d['index'], d['name'], next(
                    n['id'] for n in native if n['name'] == d['name'] and n['alive'] and n[direction]))
                    for d in devices)
            self.captures = choices(captures, 'input')
            self.outputs = choices(outputs, 'output')
            # Import existing terminal selection only once. After hot-plug, do
            # not silently bind a same-named replacement device to a stale choice.
            if self._initial_devices:
                self.selected_capture = next((d for d in self.captures if d.name == c.capture), None)
                self.selected_output = next((d for d in self.outputs if d.name == c.output), None)
                if c.live.running and c.live.config:
                    identity = c.live.config.identity
                    if (self.selected_capture is None or self.selected_output is None or
                            (self.selected_capture.native_id, self.selected_output.native_id) != identity):
                        raise AudioError("Active device identity changed. Stop LIVE and select devices again.")
            if self.selected_capture not in self.captures or self.selected_output not in self.outputs:
                self.routing_message = "Choose BlackHole 2ch and a physical stereo listening output; apply the selection."
            else:
                self.check_routing()
        except Exception as exc:
            self.routing_message = str(exc)
            if self.system_output == "Not checked":
                self.system_output = "Unavailable"
        finally:
            self._initial_devices = False

    def _fresh_selection(self, capture, output):
        # Re-enumerate through the existing verified setup filter, then compare
        # native identity to the selected token before committing a change.
        self.refresh_devices()
        if capture not in self.captures or output not in self.outputs:
            raise AudioError("Device selection is stale or missing. Refresh devices and select again.")

    def select_devices(self, capture, output, rate=48000):
        self._enter()
        self._idle()
        if rate not in (44100, 48000):
            raise AudioError("LIVE rate must be 44100 or 48000 Hz.")
        self._fresh_selection(capture, output)
        c = self.controller
        c.execute("source system")
        c.execute("input " + shlex.quote(capture.name))
        c.execute("output " + shlex.quote(output.name))
        self.selected_capture, self.selected_output, self.rate = capture, output, rate
        self.error = ""
        self.check_routing()

    def check_routing(self):
        self._enter()
        self.ready = False
        c = self.controller
        try:
            if self.selected_capture not in self.captures or self.selected_output not in self.outputs:
                raise AudioError("Select current BlackHole and physical output devices, then apply the selection.")
            routing = c._setup_routing
            native, default = routing.snapshot()
            self.system_output = next((d['name'] for d in native if d['id'] == default), "Unknown device")
            routing.validate(self.selected_capture.name, self.selected_output.name,
                             (self.selected_capture.native_id, self.selected_output.native_id))
            self.ready = True
            self.routing_message = "Routing verified. Start LIVE will independently revalidate before opening audio."
        except Exception as exc:
            self.routing_message = str(exc)
        return self.ready

    def start_live(self):
        self._enter()
        c = self.controller
        if c.live.running or c.live.stream is not None:
            raise AudioError("LIVE is already running or stopping. Stop LIVE before starting again.")
        self._idle()
        if c.source != 'system':
            raise AudioError("Apply the LIVE device selection first.")
        self._fresh_selection(self.selected_capture, self.selected_output)
        if not self.check_routing():
            raise AudioError(self.routing_message)
        # In the graphical workflow Start LIVE always begins in original
        # Bypass; effect selection is deliberately a separate next step.
        # Terminal-only commands retain their existing semantics.
        c.live.select('bypass')
        # The existing monitor independently checks channel/rate settings,
        # routing, opened native stream IDs, latency and ongoing device health.
        return c.execute(f"monitor start {self.rate}")

    def stop_live(self):
        self._enter()
        result = self.controller.live.stop()
        self.error = ""
        # Audio stop must finish without waiting for a PortAudio/CoreAudio
        # enumeration that may hang on a disconnected device. Refresh only
        # after the stream is released, on the ordinary idle poll cycle or
        # through the now-enabled Refresh / Recheck buttons.
        self.ready = False
        self.routing_message = "LIVE stopped. Recheck audio routing before restarting."
        return result

    def load_file(self, path):
        self._enter()
        self._idle()
        c = self.controller
        c.execute('source file')
        result = c.execute('load ' + shlex.quote(str(path)))
        self._file_touched = False
        self.error = ""
        return result

    def select_file_output(self, output):
        self._enter()
        self._idle()
        self.refresh_devices()
        if output not in self.outputs:
            raise AudioError("Output selection is stale. Refresh devices and select again.")
        self.controller.execute('output ' + shlex.quote(output.name))
        self.selected_output = output
        self.check_routing()

    def file_command(self, command):
        self._enter()
        if self.controller.live.running or self.controller.live.stream is not None:
            raise AudioError("Stop LIVE before using ALIVE playback.")
        if self.controller.source != 'file':
            self.controller.execute('source file')
        result = self.controller.execute(command)
        if command in ('play', 'pause', 'stop'):
            self._file_touched = True
        return result

    def live_mode(self, mode):
        self._enter()
        if mode not in ('bypass', 'velvet', 'legato', 'melt'):
            raise AudioError("Select Bypass, Velvet, Legato or Melt.")
        self.controller.live.select(mode)

    def set_monitor_volume(self, percent):
        self._enter()
        live = self.controller.live
        if live.running and not isinstance(getattr(live, 'processor', None), ListeningGainDSP):
            raise AudioError("Stop and restart LIVE from this window to enable listening volume.")
        self._monitor_volume.set_percent(percent)
        return f"ISLA listening volume: {percent}% (does not change macOS volume)."

    def poll(self):
        self._enter()
        self.controller.poll()
        return self.snapshot()

    def snapshot(self):
        self._enter()
        c, p, live = self.controller, self.controller.player, self.controller.live
        preparing = c.job is not None and not c.job.done
        live_active = live.running or live.stream is not None
        stream_active = live_active or p.stream is not None
        file_state = (UIState.PREPARING if preparing else UIState.NO_FILE if not p.buffers else
                      {'playing': UIState.PLAYING, 'paused': UIState.PAUSED, 'stopped': UIState.STOPPED,
                       'completed': UIState.STOPPED}.get(p.state, UIState.READY))
        if file_state == UIState.STOPPED and not self._file_touched:
            file_state = UIState.READY
        devices_selected = (self.selected_capture in self.captures and self.selected_output in self.outputs)
        live_state = (UIState.LIVE_STOPPING if live_active and live.halt.is_set() else
                      UIState.LIVE_RUNNING if live_active else UIState.FATAL_ERROR if live.error else
                      UIState.LIVE_READY if devices_selected and self.ready and c.source == 'system' else
                      UIState.ROUTING_INVALID if devices_selected and not self.ready else
                      UIState.LIVE_DEVICES if devices_selected else
                      UIState.LIVE_SOURCE if c.source == 'system' else UIState.LIVE_UNCONFIGURED)
        if self.error and not p.buffers and not preparing:
            file_state = UIState.RECOVERABLE_ERROR
        return ControlState(
            file_state, live_state, str(c.path or (c.job.path if c.job else '')),
            c.job.state if c.job else 'Open an audio file to begin',
            p.position / p.sr if p.sr else 0,
            len(p.buffers['original']) / p.sr if p.buffers else 0,
            p.mode, live.mode, c.source, c.capture, c.output or 'Not selected', self.system_output,
            self.captures, self.outputs, self.selected_capture, self.selected_output, self.rate,
            self.ready, self.routing_message, self.error, p.warning,
            live.status() + f"\nISLA listening volume: {self._monitor_volume.percent}% (physical output only)",
            stream_active, live_active, bool(p.buffers) and not preparing and not live_active,
            not stream_active, not stream_active,
            not stream_active and devices_selected and self.ready and c.source == 'system', self.closed,
            getattr(getattr(live, 'processor', None), 'mode', None) if live_active else None,
            self._monitor_volume.percent, live.error)

    def shutdown(self):
        self._enter()
        c = self.controller
        # Keep the lease on ANY cleanup failure. Returning a borrowed controller
        # while a worker is still stopping would allow competing streams.
        if self.owns_controller:
            c.close()
        else:
            c.live.stop()
            c.player.stop()
            if c.job is not None and not c.job.done:
                c.player.close()
                c.job.close()
                c.job = None
                c.path = None
        # Restore the exact original factory for a borrowed CLI session.
        c.live.processor_factory = self._original_live_factory
        self.closed = True
        c._window_owner = c._window_thread = None
