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
import sys
import threading

from isla.playback import AudioError
from isla.alive_listening_gain import AttenuatedALIVEBackend
from isla.vinyl_speed import VinylSpeedBackend
from isla.mix_export import MixExport
from isla.monitor_gain import ListeningGainDSP, MonitorVolume
from isla.streaming import StreamingDSP
from isla.live_engine import LiveEngineFactory, current_engine
from isla.device_refresh import eligible_devices, refresh_portaudio
from isla.buffered_capture import preferred_device_rate


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
    transport: str = ''
    default_rate: int = 48000


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
    research_pending: bool = False
    research_status: str = ''
    research_mode: str = ''
    research_intensity: int = 100
    research_summary: str = ''
    research_active: bool = False
    live_engine: str = 'production'
    live_intensity: int = 100
    live_applied_engine: str = ''
    live_research_health: str = ''
    device_status: str = ''
    file_sample_rate: int = 0
    file_channels: int = 2
    research_stage: str = 'Ready'
    research_requested: str = ''
    alive_output: str = ''
    alive_applied_mode: str = ''
    alive_health: str = ''
    live_opened_output: str = ''
    monitor_applied_volume: int | None = None
    save_pending: bool = False
    save_status: str = 'No mix saved yet.'
    save_mode: str = ''
    saved_path: str = ''
    research_workspace: bool = False
    research_previous_mode: str = ''
    alive_volume: int = 25
    alive_applied_volume: float | None = None
    save_candidate: str = ''
    live_processing_health: str = ''
    live_recovering: bool = False
    file_requested_effect: str = ''
    file_applied_effect: str = ''
    file_transition_pending: bool = False
    vinyl_slowdown: bool = False


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
        # GUI-only output adapter: the frozen BufferPlayer and the borrowed
        # terminal backend must remain intact and be restored on handoff.
        self._original_file_backend = controller.player.backend
        self._vinyl_backend = VinylSpeedBackend(self._original_file_backend)
        self._alive_gui_backend = AttenuatedALIVEBackend(self._vinyl_backend)
        from isla.remastered_session import RemasteredSession
        if not hasattr(controller, '_remastered'):
            controller._remastered = RemasteredSession(controller)
        self.preview = controller._remastered
        self.mix_export = MixExport()
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
        self.devices_need_refresh = False
        self._was_live_active = controller.live.running or controller.live.stream is not None
        self._native_signature = None
        self.device_status = 'Device discovery pending.'
        self._file_touched = controller.player.state != 'stopped'
        # A second GUI mode click during an unfinished 5 ms crossfade must
        # not force BufferPlayer to restart from the raw prior-mode buffer.
        # The control worker owns this single latest-wins pending selection.
        self._deferred_file_mode = None
        if controller._setup_routing is None:
            controller._setup_routing = getattr(controller.live.backend, 'routing', None)
        # The optional listening attenuation is a separate adapter. Never
        # change the byte-frozen LiveMonitor or StreamingDSP implementation.
        self._original_live_factory = controller.live.processor_factory
        self._monitor_volume = MonitorVolume(50)
        self._live_settings = controller.live_settings
        factory = self._original_live_factory or StreamingDSP
        if not isinstance(factory,LiveEngineFactory):
            factory = LiveEngineFactory(self._live_settings,factory)
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

    def refresh_devices(self, rescan=True):
        self._enter()
        c = self.controller
        if self._initial_devices and (c.live.running or c.live.stream is not None) and c.live.config:
            config = c.live.config
            self.selected_capture = DeviceChoice(config.input_id,config.input_name,config.identity[0])
            self.selected_output = DeviceChoice(config.output_id,config.output_name,config.identity[1])
            self.captures,self.outputs = (self.selected_capture,),(self.selected_output,)
            if self.captures and self.outputs:
                self._initial_devices = False
            self.device_status = f'LIVE opened: {config.input_name} → {config.output_name}. Stop to refresh devices.'
            return
        self._idle()
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
            signature = tuple((d['id'],d['name'],d['alive'],d['input'],d['output']) for d in native)
            if rescan or signature != self._native_signature:
                refresh_portaudio(c)
                native, default = routing.snapshot()
            self._native_signature = signature
            self.system_output = next((d['name'] for d in native if d['id'] == default), "Unknown device")
            captures, outputs = eligible_devices(native,c.player.backend.devices())
            def choices(devices, direction):
                return tuple(DeviceChoice(d['index'], d['name'], d['native_id'],d.get('transport',''),
                                          preferred_device_rate(d))
                    for d in devices)
            self.captures = choices(captures, 'input')
            self.outputs = choices(outputs, 'output')
            # Import existing terminal selection only once. After hot-plug, do
            # not silently bind a same-named replacement device to a stale choice.
            if self._initial_devices:
                self.selected_capture = next((d for d in self.captures if d.name == c.capture), None)
                self.selected_output = next((d for d in self.outputs if d.name == c.output), None)
                if c.live.config is None and self.selected_output is not None:
                    self.rate = self.selected_output.default_rate
                if c.live.running and c.live.config:
                    identity = c.live.config.identity
                    if (self.selected_capture is None or self.selected_output is None or
                            (self.selected_capture.native_id, self.selected_output.native_id) != identity):
                        raise AudioError("Active device identity changed. Stop LIVE and select devices again.")
            else:
                def rebind(token, choices):
                    return next((d for d in choices if token is not None and
                                 (d.native_id,d.name) == (token.native_id,token.name)),token)
                self.selected_capture = rebind(self.selected_capture,self.captures)
                self.selected_output = rebind(self.selected_output,self.outputs)
            if self.selected_capture is None and len(self.captures) == 1:
                self.selected_capture = self.captures[0]
            if self.captures and self.outputs:
                self._initial_devices = False
            self.device_status = (f'Device list refreshed: {len(self.outputs)} physical listening output(s). '
                                  f"Applied output: {c.output or 'choose and apply Step 2' }.")
            if self.selected_capture not in self.captures or self.selected_output not in self.outputs:
                self.routing_message = "Choose BlackHole 2ch and a physical stereo listening output; apply the selection."
            else:
                self.check_routing()
            if not self.captures:
                self.routing_message = 'BlackHole 2ch is unavailable. Physical outputs remain listed in Step 2; connect BlackHole and refresh.'
        except Exception as exc:
            self.routing_message = str(exc)
            if self.system_output == "Not checked":
                self.system_output = "Unavailable"
            self.device_status = 'Device refresh needs attention: ' + str(exc)
        finally:
            self.devices_need_refresh = False

    def _fresh_selection(self, capture, output):
        # Re-enumerate through the existing verified setup filter, then compare
        # native identity to the selected token before committing a change.
        self.refresh_devices()
        capture = next((d for d in self.captures if capture and (d.native_id,d.name) == (capture.native_id,capture.name)),None)
        output = next((d for d in self.outputs if output and (d.native_id,d.name) == (output.native_id,output.name)),None)
        if capture is None or output is None:
            raise AudioError("Device selection is stale or missing. Refresh devices and select again.")
        return capture,output

    def select_devices(self, capture, output, rate=48000):
        self._enter()
        self._idle()
        if rate not in (44100, 48000):
            raise AudioError("LIVE rate must be 44100 or 48000 Hz.")
        capture,output = self._fresh_selection(capture, output)
        c = self.controller
        self._deferred_file_mode = None
        self.preview.reset()
        c.execute("source system")
        c.execute("input " + shlex.quote(capture.name))
        c.execute("output " + shlex.quote(output.name))
        self.selected_capture, self.selected_output, self.rate = capture, output, rate
        self.device_status = f'Applied LIVE devices: {capture.name} → {output.name} at {rate:,} Hz.'
        self.error = ""
        self.check_routing()

    def auto_setup_devices(self):
        """Find one unambiguous listening path; never change macOS routing."""
        self._enter()
        self._idle()
        self.refresh_devices()
        if len(self.captures) != 1:
            raise AudioError('BlackHole 2ch is not available. Connect or install BlackHole 2ch, then try Find Connected Devices again. ALIVE file playback does not need BlackHole.')
        if not self.outputs:
            raise AudioError('No listening device found. Connect your headphones or speakers, then click Find Connected Devices again.')
        output = self._suggest_output(self.outputs, self.selected_output)
        if output is None:
            raise AudioError('Several listening devices are connected. Choose your headphones or speakers in Step 1, then click Use These Devices.')
        self.select_devices(self.captures[0], output, output.default_rate)
        return f'Found and selected {output.name} at {self.rate:,} Hz. ' + (
            'Your setup is ready. Click Start LIVE when you want to listen.' if self.ready else
            'Next, open Mac Sound Settings and choose BlackHole 2ch as the Mac output, then Check My Setup.')

    @staticmethod
    def _suggest_output(outputs, preferred=None):
        if preferred in outputs:
            return preferred
        external = [device for device in outputs if device.transport != 'bltn']
        if len(external) == 1:
            return external[0]
        return outputs[0] if len(outputs) == 1 else None

    def _prepare_file_output(self, requested=None):
        """Resolve and validate ALIVE's output before opening its first stream.

        Capture and the Mac's system-audio route are independent of local-file
        playback. All enumeration and device checks stay on the owning worker.
        """
        self._idle()
        self.refresh_devices()
        if not self.outputs and sys.platform != 'darwin' and self.controller._setup_routing is None:
            # Portable ALIVE has no CoreAudio inventory. Its backend retains
            # the existing OS-default output and verifies rate/channels at open.
            return
        c, p = self.controller, self.controller.player
        sd = getattr(self._original_file_backend, 'sd', None)
        def verify(device):
            if sd is None:
                return
            try:
                sd.check_output_settings(device=device.index, samplerate=p.sr,
                    channels=p.buffers['original'].shape[1], dtype='float32')
            except Exception as exc:
                raise AudioError(f'{device.name} cannot play this recording at {p.sr:,} Hz. Choose another listening output, then click Play. Details: {exc}') from exc
        if requested is not None:
            output = next((device for device in self.outputs if
                (device.native_id, device.name) == (requested.native_id, requested.name)), None)
            if output is None:
                raise AudioError('Your chosen listening device is no longer connected. Choose an available output below, then click Play.')
            verify(output)
        else:
            compatible, rejected = [], []
            for device in self.outputs:
                try:
                    verify(device)
                    compatible.append(device)
                except AudioError as exc:
                    rejected.append(exc)
            if self.outputs and not compatible:
                raise rejected[0]
            output = self._suggest_output(compatible, self.selected_output)
        if output is None:
            if not self.outputs:
                raise AudioError('No listening device found. Connect your headphones or speakers, then click Play again.')
            raise AudioError('Several listening devices are connected. Choose your headphones or speakers below, then click Play.')
        # Reuse the normal selector; hardware opens only after all checks pass.
        c.execute('output ' + shlex.quote(str(output.index)))
        if self.selected_output != output:
            # A file's sample rate is independent of the shared listening
            # device's LIVE rate. Keep an explicit rate for an unchanged device.
            self.rate = output.default_rate
        self.selected_output = output
        self.check_routing()  # Advisory LIVE status; its result never gates ALIVE.
        self.device_status = f'Connected: {output.name}. ALIVE is ready to play.'

    def check_routing(self):
        self._enter()
        self.ready = False
        c = self.controller
        try:
            routing = c._setup_routing
            native, default = routing.snapshot()
            self.system_output = next((d['name'] for d in native if d['id'] == default), "Unknown device")
            if self.selected_capture not in self.captures or self.selected_output not in self.outputs:
                raise AudioError("Select current BlackHole and physical output devices, then apply the selection.")
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
        if ((c.job is not None and not c.job.done) or self.preview.job is not None
                or self.mix_export.pending):
            raise AudioError('Finish or cancel ALIVE preparation or Save Mix before starting LIVE.')
        self.selected_capture,self.selected_output = self._fresh_selection(self.selected_capture, self.selected_output)
        if not self.check_routing():
            raise AudioError(self.routing_message)
        # ALIVE and LIVE share a verified listening-device choice, but own
        # different streams. Switch source only on this explicit Start, after
        # ALIVE has released its output and the saved identities still match.
        self._deferred_file_mode = None
        self.preview.reset()
        c.execute('source system')
        c.execute('input ' + shlex.quote(self.selected_capture.name))
        c.execute('output ' + shlex.quote(str(self.selected_output.index)))
        # In the graphical workflow Start LIVE always begins in original
        # Bypass; effect selection is deliberately a separate next step.
        # Terminal-only commands retain their existing semantics.
        c.live.select('bypass')
        # The existing monitor independently checks channel/rate settings,
        # routing, opened native stream IDs, latency and ongoing device health.
        result = c.execute(f"monitor start {self.rate}")
        config = c.live.config
        self._was_live_active = True
        self.device_status = f'LIVE opened: {config.input_name} → {config.output_name} at {config.rate:,} Hz.'
        return result

    def stop_live(self):
        self._enter()
        result = self.controller.live.stop()
        self.error = ""
        # Audio stop must finish without waiting for a PortAudio/CoreAudio
        # enumeration that may hang on a disconnected device. Refresh only
        # after the stream is released, on the ordinary idle poll cycle or
        # through the now-enabled Refresh / Recheck buttons.
        self.ready = False
        self.devices_need_refresh = True
        self.device_status = 'LIVE stopped; refreshing available listening devices…'
        self.routing_message = "LIVE stopped. Recheck audio routing before restarting."
        return result

    def load_file(self, path):
        self._enter()
        self._idle()
        if self.mix_export.pending:
            raise AudioError('Finish or cancel Save Mix before opening another file.')
        c = self.controller
        self._deferred_file_mode = None
        self.preview.reset()
        c.execute('source file')
        result = c.execute('load ' + shlex.quote(str(path)))
        self._vinyl_backend.slowdown = False
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
        if self.selected_output != output:
            self.rate = output.default_rate
        self.selected_output = output
        self.check_routing()

    def file_command(self, command, output=None):
        self._enter()
        if self.controller.live.running or self.controller.live.stream is not None:
            raise AudioError("Stop LIVE before using ALIVE playback.")
        if self.controller.source != 'file':
            self._deferred_file_mode = None
            self.controller.execute('source file')
        if self.preview.workspace and (command == 'bypass' or command.startswith('mode ')):
            raise AudioError('Return to Previous Mode before selecting traditional processing.')
        if command == 'stop' and self.preview.workspace:
            self.preview.cancel()
        p = self.controller.player
        target = ('original' if command == 'bypass' else
                  command[5:] if command.startswith('mode ') else None)
        if (target in ('original', 'velvet', 'legato', 'melt')
                and p.state == 'playing' and p.stream is not None
                and getattr(p, '_fade_pos', 0) < len(p._fade)):
            self.controller._ready()
            if target not in p.buffers:
                raise AudioError('Selected ALIVE mode is not prepared.')
            # A new click does not interrupt the active audible mixture.
            # Repeated clicks coalesce: the latest valid selection wins.
            self._deferred_file_mode = command
            return f'{target.title()} requested; waiting for the current audio fade to finish.'
        if target is not None or command in ('play', 'pause', 'stop'):
            self._deferred_file_mode = None
        if command == 'play':
            p.refresh()
            self.controller._ready()
            if p.stream is None:
                self._prepare_file_output(output)
            # Install the GUI-only output wrapper before stream creation on
            # every Play/resume. It scales final PCM without modifying the
            # byte-frozen BufferPlayer or any source/research buffers.
            self.controller.player.backend = self._alive_gui_backend
        result = self.controller.execute(command)
        if command in ('play', 'pause', 'stop'):
            self._file_touched = True
        return result

    def enter_remastered(self):
        self._enter()
        if self._vinyl_backend.slowdown:
            raise AudioError('Turn off Vinyl-style slowdown before entering Remastered research.')
        result = self.preview.enter()
        self._deferred_file_mode = None
        return result

    def return_previous_mode(self):
        self._enter()
        return self.preview.return_previous()

    def set_alive_volume(self, percent):
        self._enter()
        p = self.controller.player
        if p.stream is not None and p.backend is not self._alive_gui_backend:
            raise AudioError('Stop and resume ALIVE from this window to enable listening volume.')
        self._alive_gui_backend.set_percent(percent)
        return f'ALIVE listening volume: {percent}%.'

    def set_vinyl_slowdown(self, enabled):
        """Commit 50% vinyl playback from the worker, preserving the source cursor.

        The output stream is stopped before changing its playback adapter.
        Both pitch and tempo fall together; no source PCM or research data changes.
        """
        self._enter()
        if type(enabled) is not bool:
            raise AudioError('Vinyl-style slowdown expects an on/off selection.')
        c, p = self.controller, self.controller.player
        if c.source != 'file' or not p.buffers or (c.job is not None and not c.job.done):
            raise AudioError('Load and prepare an ALIVE song before changing speed.')
        if c.live.running or c.live.stream is not None:
            raise AudioError('Stop LIVE before changing ALIVE speed.')
        if self.preview.workspace or self.preview.job is not None:
            raise AudioError('Return from Remastered research before changing speed.')
        if self.mix_export.pending:
            raise AudioError('Finish or cancel Save Mix before changing speed.')
        # A finished callback may precede the next periodic UI poll.
        p.refresh()
        if self._deferred_file_mode is not None or (p.stream is not None and
                (getattr(p, '_current', None) is not p._selected or
                 p._fade_pos < len(p._fade))):
            raise AudioError('Wait for the current mode transition to finish.')
        old = self._vinyl_backend.slowdown
        if old == enabled:
            return 'Vinyl-style slowdown: 50%.' if enabled else 'Normal ALIVE speed: 100%.'
        playing = p.state == 'playing' and p.stream is not None
        if playing and p.backend is not self._alive_gui_backend:
            raise AudioError('Resume ALIVE from the Control Center before changing speed.')
        if playing:
            p.pause()  # Captures audible sample cursor and releases old stream.
            # EOF may arrive between refresh() above and pause()'s own refresh.
            playing = p.state == 'paused'
        self._vinyl_backend.slowdown = enabled
        if playing:
            try:
                p.play()  # Same sample cursor and mode; native rate unchanged.
            except Exception:
                self._vinyl_backend.slowdown = old
                try:
                    p.play()  # Best-effort recovery with the previous setting.
                except Exception:
                    pass
                raise
        return ('Vinyl-style slowdown active: 50% speed and lower pitch.' if enabled
                else 'Vinyl-style slowdown off: normal 100% speed and pitch.')

    def prepare_remastered(self, mode, intensity):
        self._enter()
        return self.preview.prepare(mode, intensity)

    def save_mix(self, destination):
        """Export one committed ALIVE mode, never live routing or listening gain."""
        self._enter()
        c, p = self.controller, self.controller.player
        if c.source != 'file' or c.live.running or c.live.stream is not None:
            raise AudioError('Select ALIVE and stop LIVE before saving a mix.')
        if self.preview.job is not None:
            raise AudioError('Wait for Remastered preparation or cancel it before saving.')
        if not p.buffers or p.mode not in p.buffers:
            raise AudioError('Prepare a local recording and choose an ALIVE mode first.')
        if (p.stream is not None and p.state == 'playing'
                and (getattr(p, '_current', None) is not p._selected
                     or p._fade_pos < len(p._fade))):
            raise AudioError('Wait for the active mode switch to finish before saving.')
        # The selected buffer is immutable and already prepared/validated.
        # This intentionally excludes Control Center's 25% speaker attenuation.
        return self.mix_export.start(p.buffers[p.mode], p.sr, p.mode, destination)

    def cancel_mix_save(self):
        self._enter()
        return self.mix_export.cancel()

    def cancel_remastered(self):
        self._enter()
        if self.preview.workspace and self.preview.job is None and self.controller.player.mode.startswith('remastered_'):
            raise AudioError('Remastered is active; use Return to Previous Mode.')
        self.preview.cancel()

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

    def set_live_processing(self, engine, intensity):
        self._enter()
        live = self.controller.live
        if live.running and current_engine(getattr(live,'processor',None)) is None:
            raise AudioError('Stop and restart LIVE from this window to enable Remastered processing.')
        self._live_settings.set(engine,intensity)
        return f'LIVE requested: {engine.title()}, {intensity}% permitted Remastered depth.'

    def poll(self):
        self._enter()
        self.controller.poll()
        self.preview.poll()
        if self._deferred_file_mode is not None:
            p = self.controller.player
            if (self.controller.source != 'file' or p.state != 'playing'
                    or p.stream is None or self.preview.workspace):
                self._deferred_file_mode = None
            elif (getattr(p, '_current', None) is p._selected
                    and p._fade_pos >= len(p._fade)):
                # Only the control worker publishes a new selected buffer.
                # The callback has completed its previous 5 ms fade.
                command = self._deferred_file_mode
                self._deferred_file_mode = None
                self.controller.execute(command)
        active = self.controller.live.running or self.controller.live.stream is not None
        if self._was_live_active and not active:
            self.devices_need_refresh = True
        self._was_live_active = active
        return self.snapshot()

    def snapshot(self):
        self._enter()
        c, p, live = self.controller, self.controller.player, self.controller.live
        engine = current_engine(getattr(live,'processor',None))
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
                      UIState.LIVE_READY if devices_selected and self.ready and not stream_active else
                      UIState.ROUTING_INVALID if devices_selected and not self.ready else
                      UIState.LIVE_DEVICES if devices_selected else
                      UIState.LIVE_SOURCE if c.source == 'system' else UIState.LIVE_UNCONFIGURED)
        if self.error and not p.buffers and not preparing:
            file_state = UIState.RECOVERABLE_ERROR
        if p.stream is None:
            file_mode_status = 'No active stream'
        elif getattr(p, '_current', None) is not p._selected:
            file_mode_status = 'previous buffer — selected mode awaits callback'
        else:
            file_mode_status = p.mode + (
                ' — crossfading' if p._fade_pos < len(p._fade) else ''
            )
        if p.stream is not None and self._deferred_file_mode:
            queued_mode = self._deferred_file_mode.replace('mode ', '')
            file_mode_status += '; queued: ' + queued_mode.title()
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
            (not stream_active and devices_selected and self.ready and not preparing
             and self.preview.job is None and not self.mix_export.pending), self.closed,
            getattr(getattr(live, 'processor', None), 'mode', None) if live_active else None,
            self._monitor_volume.percent, live.error,
            self.preview.job is not None, self.preview.state,
            self.preview.applied.mode if self.preview.applied else '',
            self.preview.applied.intensity if self.preview.applied else 100,
            self.preview.summary, p.mode.startswith('remastered_'),
            self._live_settings.request.engine,self._live_settings.request.intensity,
            getattr(getattr(engine,'applied',None),'engine','') if live_active else '',
            getattr(engine,'diagnostics','') if live_active else '',self.device_status,
            p.sr if p.buffers else 0,
            p.buffers['original'].shape[1] if p.buffers else 0,
            self.preview.stage,
            (f'{self.preview.requested.mode} / {self.preview.requested.intensity}% depth'
             if self.preview.requested else ''),
            p.output,
            file_mode_status,
            self._alive_gui_backend.diagnostics(),
            (f'{live.config.output_name} (PortAudio {live.config.output_id}; '
             f'native {live.config.identity[1]})' if live.config else 'Not opened'),
            round(live.processor._applied * 100)
            if isinstance(getattr(live, 'processor', None), ListeningGainDSP) else None,
            self.mix_export.pending, self.mix_export.status,
            self.mix_export.mode, self.mix_export.saved_path,
            self.preview.workspace, self.preview.previous_mode or '',
            self._alive_gui_backend.output_level_percent,
            self._alive_gui_backend.applied_percent
            if p.backend is self._alive_gui_backend and p.stream is not None else None,
            ('Unavailable — preparation pending' if self.preview.job is not None else
             'Unavailable — mode transition pending' if p.stream is not None and
             (getattr(p, '_current', None) is not p._selected or p._fade_pos < len(p._fade)) else
             p.mode + ' — prepared buffer, unity export' if p.buffers else 'Unavailable — no recording'),
            live_processing_health=getattr(engine, 'processing_telemetry',
                'No LIVE processor observations yet; start LIVE to measure worker workload.'),
            live_recovering=live._recovering,
            file_requested_effect=(self._deferred_file_mode.replace('mode ', '')
                                   if self._deferred_file_mode else p.mode),
            file_applied_effect=(next((name for name, buffer in p.buffers.items()
                                if buffer is getattr(p, '_current', None)), '')
                                if p.stream is not None else ''),
            file_transition_pending=bool(p.stream is not None and
                (getattr(p, '_current', None) is not p._selected or
                 p._fade_pos < len(p._fade) or self._deferred_file_mode)),
            vinyl_slowdown=self._vinyl_backend.slowdown)

    def shutdown(self):
        self._enter()
        c = self.controller
        self._deferred_file_mode = None
        self.preview.reset()
        self.mix_export.cancel()  # Abort partial exports before returning ownership.
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
        # Restore both original backends only AFTER all audio streams stop.
        # Borrowed terminal sessions must not inherit GUI attenuation.
        c.player.backend = self._original_file_backend
        c.live.processor_factory = self._original_live_factory
        self.closed = True
        c._window_owner = c._window_thread = None
