"""Qt Widgets presentation. All audio operations execute on one daemon worker.

The event thread consumes immutable snapshots only. It never enumerates devices,
prepares audio, waits on a worker or closes an audio stream. A stalled operation
leaves the window responsive with explicit diagnostics and retains the exclusive
session lease until cleanup completes; it never hands a busy engine to the CLI.
"""
from __future__ import annotations

import queue
from collections import deque
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QGridLayout, QLabel, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget,
)

from isla.control import ControlService
from isla.playback import SoundDeviceBackend
from isla.terminal import TerminalController

SOUND_SETTINGS_URL = 'x-apple.systempreferences:com.apple.Sound-Settings.extension'
MANUAL_SETTINGS = 'Open Apple menu → System Settings → Sound → Output and select BlackHole 2ch. Keep physical speakers/headphones selected inside ISLA.'
RESTORE_OUTPUT = 'After LIVE stops: if macOS still uses BlackHole, restore your normal speakers/headphones in System Settings → Sound → Output to hear ordinary Mac audio.'
_application = None  # Reuse our Qt instance across terminal window/close cycles.


class AudioApplication(QApplication):
    """Route desktop Quit through the same asynchronous audio cleanup as Close."""
    window = None

    def event(self, event):
        if (event.type() == QEvent.Type.Quit and self.window is not None
                and not (self.window.closed_cleanly or self.window.failed_initialize)):
            self.window.close()
            return True
        return super().event(event)


def open_sound_settings():
    """Ask LaunchServices to open the Sound pane; never edit audio properties."""
    if sys.platform != 'darwin':
        raise RuntimeError('Sound Settings is available on macOS. ' + MANUAL_SETTINGS)
    try:
        subprocess.run(['/usr/bin/open', SOUND_SETTINGS_URL], check=True, timeout=5,
                       capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('Could not open Sound Settings. ' + MANUAL_SETTINGS) from exc
    return MANUAL_SETTINGS


class CommandWorker:
    """Bounded command queue; no Qt objects or widgets cross into this thread."""
    def __init__(self, controller=None, factory=None):
        self.commands = queue.Queue(maxsize=1)
        self.events = queue.Queue()
        self.controller = controller
        self.factory = factory or (lambda: TerminalController(SoundDeviceBackend()))
        self.service = None
        self._sequence = 0
        self._last_device_refresh = 0.0
        self.thread = threading.Thread(target=self._run, name='isla-control', daemon=True)

    def start(self):
        self.thread.start()

    def submit(self, action, *args):
        self.commands.put_nowait((action, args))

    def _publish(self):
        self._sequence += 1
        self.events.put(('state', (self._sequence, self.service.snapshot())))

    def _run(self):
        try:
            self._loop()
        except BaseException as exc:
            # Unexpected worker failures must not strand an owned engine.
            message = f'Control worker failed: {exc}'
            try:
                if self.service is not None and not self.service.closed:
                    self.service.shutdown()
            except BaseException as cleanup:
                self.events.put(('worker_failed', message + f'; cleanup incomplete: {cleanup}'))
            else:
                self.events.put(('fatal_closed', message))

    def retry_cleanup(self):
        """Only after a dead command thread, transfer its lease for cleanup."""
        if self.thread.is_alive():
            return False
        self.service.controller._window_thread = None
        def cleanup():
            try:
                self.service.shutdown()
                self.events.put(('closed', None))
            except BaseException as exc:
                self.events.put(('worker_failed', f'Cleanup incomplete: {exc}'))
        self.thread = threading.Thread(target=cleanup, name='isla-cleanup', daemon=True)
        self.thread.start()
        return True

    def _loop(self):
        try:
            controller = self.controller if self.controller is not None else self.factory()
            self.service = ControlService(controller, owns_controller=self.controller is None)
            self.service.refresh_devices()
            self.service.poll()
            self._publish()
            self.events.put(('done', 'initialize'))
        except Exception as exc:
            if self.service is not None:
                # Preparation errors must remain recoverable in the window.
                self.service.error = str(exc)
                self._publish()
                self.events.put(('done', 'initialize'))
            else:
                self.events.put(('unavailable', str(exc)))
                return
        self._last_device_refresh = time.monotonic()
        while True:
            try:
                action, args = self.commands.get(timeout=.1)
            except queue.Empty:
                action, args = 'poll', ()
            try:
                if action == 'shutdown':
                    self.service.shutdown()
                    self.events.put(('closed', None))
                    return
                if action == 'settings':
                    self.events.put(('message', open_sound_settings()))
                elif action == 'poll':
                    state = self.service.poll()
                    now = time.monotonic()
                    if now - self._last_device_refresh > 2:
                        # CoreAudio/PortAudio enumeration can block in a native
                        # driver. Never do a background rescan while a stream is
                        # running: it delays Stop and competes with LIVE audio.
                        # The LIVE worker still validates its routing itself.
                        self._last_device_refresh = now
                        if not state.stream_active:
                            self.service.refresh_devices()
                else:
                    method = {'load': self.service.load_file, 'file': self.service.file_command,
                              'live_mode': self.service.live_mode, 'devices': self.service.select_devices,
                              'file_output': self.service.select_file_output,
                              'refresh': self.service.refresh_devices, 'start': self.service.start_live,
                              'stop': self.service.stop_live, 'volume': self.service.set_monitor_volume,
                              'research': self.service.prepare_remastered,
                              'cancel_research': self.service.cancel_remastered}[action]
                    result = method(*args)
                    self.service.error = ''
                    if result:
                        self.events.put(('message', str(result)))
            except Exception as exc:
                self.service.error = str(exc)
                self.events.put(('error', (action, str(exc))))
            self._publish()
            if action != 'poll':
                self.events.put(('done', action))


def label(text=''):
    result = QLabel(text)
    result.setWordWrap(True)
    result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    # Paths/device names/errors are plain text, never interpreted as HTML.
    result.setTextFormat(Qt.TextFormat.PlainText)
    return result


class ControlWindow(QMainWindow):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self._mode_groups = {}
        self.state = None
        self._state_sequence = 0
        self._pending_live_mode = None
        self._mode_requests = deque()
        self._mode_inflight = None
        self._live_mode_error = ''
        self._stop_requested = False
        self.busy = 'initialize'
        self.started = time.monotonic()
        self.closing = self.closed_cleanly = self.failed_initialize = False
        self.result_code = 0
        self.cleanup_error = ''
        self.worker_failed = False
        self.setWindowTitle('ISLA — Audio Control Center')
        self.resize(1040, 830)
        root = QWidget()
        outer = QVBoxLayout(root)
        title = label('ISLA — Audio Control Center')
        font = title.font()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        outer.addWidget(title)
        outer.addWidget(label('ALIVE plays a prepared local file. LIVE listens to Mac system audio through BlackHole. One session owns the audio.'))
        self.activity = label('Connecting to the audio session…')
        outer.addWidget(self.activity)
        self.global_error = label()
        outer.addWidget(self.global_error)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        contents = QWidget()
        columns = QHBoxLayout(contents)
        columns.setSpacing(18)
        columns.addWidget(self._file_panel(), 2)
        columns.addWidget(self._live_panel(), 3)
        columns.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(contents)
        outer.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        self.refresh = QPushButton('Refresh Devices')
        self.refresh.clicked.connect(lambda: self.submit('refresh'))
        bottom.addWidget(self.refresh)
        bottom.addStretch()
        self.close_button = QPushButton('Close Window / Return to CLI')
        self.close_button.clicked.connect(self.close)
        bottom.addWidget(self.close_button)
        outer.addLayout(bottom)
        self.setCentralWidget(root)
        QShortcut(QKeySequence.StandardKey.Open, self, self.choose_file)
        QShortcut(QKeySequence.StandardKey.Close, self, self.close)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.drain_events)
        self.timer.start()
        self.apply_state()

    def _modes(self, layout, source):
        row = QGridLayout()
        buttons = {}
        # Exclusive selection is a mode choice, not four independent on/off
        # switches. Backend snapshots remain authoritative after each click.
        group = QButtonGroup(self)
        group.setExclusive(True)
        self._mode_groups[source] = group
        for name, value in [('Original / Bypass', 'bypass'), ('Velvet', 'velvet'), ('Legato', 'legato'), ('Melt', 'melt')]:
            button = QPushButton(name)
            button.setCheckable(True)
            group.addButton(button)
            if source == 'file':
                command = 'bypass' if value == 'bypass' else 'mode ' + value
                button.clicked.connect(lambda checked=False, cmd=command: self.submit('file', cmd))
            else:
                button.clicked.connect(lambda checked=False, mode=value: self._choose_live_mode(mode))
            index = len(buttons)
            row.addWidget(button, index // 2, index % 2)
            buttons[value] = button
        layout.addLayout(row)
        return buttons

    def _file_panel(self):
        panel = QGroupBox('ALIVE — Local Audio File')
        box = QVBoxLayout(panel)
        self.open_file = QPushButton('Open WAV File…')
        self.open_file.clicked.connect(self.choose_file)
        box.addWidget(self.open_file)
        self.filename = label('No file selected')
        self.file_status = label('Open an audio file to begin')
        box.addWidget(self.filename)
        box.addWidget(self.file_status)
        self.file_error = label()
        box.addWidget(self.file_error)
        row = QHBoxLayout()
        self.play, self.pause, self.stop_file = (QPushButton(text) for text in ('Play', 'Pause', 'Stop'))
        for button, cmd in [(self.play, 'play'), (self.pause, 'pause'), (self.stop_file, 'stop')]:
            button.clicked.connect(lambda checked=False, command=cmd: self.submit('file', command))
            row.addWidget(button)
        box.addLayout(row)
        self.position = label('0:00 / 0:00')
        box.addWidget(self.position)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        box.addWidget(self.progress)
        self.file_modes = self._modes(box, 'file')
        self.research_toggle = QPushButton('Show v4.0 Remastered Research Preview')
        self.research_toggle.setCheckable(True)
        box.addWidget(self.research_toggle)
        research = QGroupBox('v4.0 Remastered — Research Preview')
        self.research_panel = research
        research.setVisible(False)
        self.research_toggle.toggled.connect(research.setVisible)
        self.research_toggle.toggled.connect(lambda shown: self.research_toggle.setText(
            ('Hide' if shown else 'Show') + ' v4.0 Remastered Research Preview'))
        research_box = QVBoxLayout(research)
        research_box.addWidget(label('0% is exact original; 100% is the governed research baseline. Intensity controls permitted DSP depth, not volume.'))
        self.research_mode = QComboBox()
        self.research_mode.setAccessibleName('Remastered research mode')
        for mode in ('velvet', 'legato', 'melt'):
            self.research_mode.addItem(mode.title() + ' Remastered', mode)
        research_box.addWidget(self.research_mode)
        # Integer ticks map exactly to 5%; mouse and keyboard cannot request
        # an off-grid value. Draft choices are not overwritten by health polls.
        self.research_intensity = QSlider(Qt.Orientation.Horizontal)
        self.research_intensity.setRange(0, 20)
        self.research_intensity.setSingleStep(1)
        self.research_intensity.setPageStep(1)
        self.research_intensity.setValue(20)
        self.research_intensity.setAccessibleName('Remastered intensity, 0 to 100 percent in 5 percent steps')
        self.research_intensity_value = label('100% permitted depth')
        self.research_intensity.valueChanged.connect(
            lambda value: self.research_intensity_value.setText(f'{value * 5}% permitted depth'))
        self.research_intensity.sliderReleased.connect(self._prepare_research)
        research_box.addWidget(self.research_intensity)
        research_box.addWidget(self.research_intensity_value)
        row = QHBoxLayout()
        self.apply_research = QPushButton('Prepare / Apply Remastered')
        self.apply_research.clicked.connect(self._prepare_research)
        self.cancel_research = QPushButton('Cancel Preparation')
        self.cancel_research.clicked.connect(lambda: self.submit('cancel_research'))
        row.addWidget(self.apply_research)
        row.addWidget(self.cancel_research)
        research_box.addLayout(row)
        self.research_status, self.research_summary = label(), label()
        research_box.addWidget(self.research_status)
        research_box.addWidget(self.research_summary)
        research_box.addWidget(label('44.1/48 kHz mono/stereo, up to 30 seconds. Audio continues during preparation. Original / Bypass restores the source. REVISE / INCONCLUSIVE; listening acceptance pending.'))
        box.addWidget(research)
        box.addWidget(label('Listening output (shared with LIVE)'))
        self.file_output = QComboBox()
        self.file_output.setAccessibleName('ALIVE physical listening output')
        box.addWidget(self.file_output)
        self.apply_output = QPushButton('Use Listening Output')
        self.apply_output.clicked.connect(lambda: self.submit('file_output', self.file_output.currentData()))
        box.addWidget(self.apply_output)
        box.addWidget(label('ALIVE can use the system default output without BlackHole. Physical output choices are offered when verified by macOS. Stop audio before changing devices.'))
        # Use spare left-panel space for LIVE listening attenuation. This does
        # not alter BlackHole capture gain, other apps or macOS output volume.
        volume_group = QGroupBox('LIVE Listening Volume')
        volume_box = QVBoxLayout(volume_group)
        volume_box.addWidget(label('Controls only the ISLA sound sent to selected headphones/speakers. BlackHole capture and macOS volume do not change. 100% is original/unity; 0% is muted.'))
        self.monitor_volume = QSlider(Qt.Orientation.Horizontal)
        self.monitor_volume.setAccessibleName('LIVE listening volume (0 to 100 percent)')
        self.monitor_volume.setRange(0, 100)
        self.monitor_volume.setValue(100)
        self.monitor_volume_value = label('100%')
        self.monitor_volume.valueChanged.connect(lambda value: self.monitor_volume_value.setText(f'{value}%'))
        self.monitor_volume.sliderReleased.connect(self._apply_volume)
        volume_box.addWidget(self.monitor_volume)
        row = QHBoxLayout()
        row.addWidget(self.monitor_volume_value)
        self.apply_volume = QPushButton('Apply Volume')
        self.apply_volume.clicked.connect(self._apply_volume)
        row.addWidget(self.apply_volume)
        self.mute_volume = QPushButton('Mute')
        self.mute_volume.clicked.connect(self._toggle_mute)
        row.addWidget(self.mute_volume)
        volume_box.addLayout(row)
        self.monitor_volume_status = label('LIVE listening level: 100% (unity)')
        volume_box.addWidget(self.monitor_volume_status)
        box.addWidget(volume_group)
        box.addStretch()
        return panel

    def _live_panel(self):
        panel = QGroupBox('LIVE — Mac System Audio')
        box = QVBoxLayout(panel)
        form = QFormLayout()
        self.capture = QComboBox()
        self.capture.setAccessibleName('Step 1 BlackHole capture source')
        self.output = QComboBox()
        self.output.setAccessibleName('Step 2 physical stereo listening device')
        self.rate = QComboBox()
        for rate in (44100, 48000):
            self.rate.addItem(f'{rate:,} Hz', rate)
        self.rate.setCurrentIndex(1)
        self.rate.setAccessibleName('LIVE sample rate')
        form.addRow('Step 1 — Capture Source', self.capture)
        form.addRow('Step 2 — Physical Listening Device', self.output)
        form.addRow('Sample rate', self.rate)
        box.addLayout(form)
        self.apply_devices = QPushButton('Apply LIVE Devices / Select LIVE Source')
        self.apply_devices.clicked.connect(lambda: self.submit('devices', self.capture.currentData(), self.output.currentData(), self.rate.currentData()))
        box.addWidget(self.apply_devices)
        box.addWidget(label('Step 3 — macOS Sound Routing'))
        self.routing = label('Routing has not been checked.')
        box.addWidget(self.routing)
        box.addWidget(label('Mac audio → BlackHole 2ch → ISLA processing → selected physical speakers/headphones. ISLA never changes macOS audio settings.'))
        row = QHBoxLayout()
        self.settings = QPushButton('Open Sound Settings')
        self.settings.clicked.connect(lambda: self.submit('settings'))
        self.recheck = QPushButton('Recheck Audio Routing')
        self.recheck.clicked.connect(lambda: self.submit('refresh'))
        row.addWidget(self.settings)
        row.addWidget(self.recheck)
        box.addLayout(row)
        self.next_action = label(MANUAL_SETTINGS)
        box.addWidget(self.next_action)
        box.addWidget(label('Step 4 — Start Monitoring'))
        row = QHBoxLayout()
        self.start_live = QPushButton('Start LIVE')
        self.start_live.clicked.connect(lambda: self.submit('start'))
        self.stop_live = QPushButton('Stop LIVE')
        self.stop_live.clicked.connect(self._request_live_stop)
        row.addWidget(self.start_live)
        row.addWidget(self.stop_live)
        box.addLayout(row)
        # A single effect dropdown replaces four mode buttons. Start/Stop
        # remain explicit, independent actions for audio safety.
        self.live_mode_choice = QComboBox()
        self.live_mode_choice.setAccessibleName('Step 4 LIVE sound effect')
        for name, mode in (('Original / Bypass', 'bypass'), ('Velvet', 'velvet'),
                           ('Legato', 'legato'), ('Melt', 'melt')):
            self.live_mode_choice.addItem(name, mode)
        self.live_mode_choice.activated.connect(
            lambda index: self._choose_live_mode(self.live_mode_choice.itemData(index)))
        box.addWidget(label('LIVE sound effect — choose processing or reset to Original'))
        box.addWidget(self.live_mode_choice)
        self.reset_live_mode = QPushButton('Reset to Original')
        self.reset_live_mode.clicked.connect(lambda: self._choose_live_mode('bypass'))
        box.addWidget(self.reset_live_mode)
        self.live_mode_status = label('Select a mode for LIVE monitoring.')
        box.addWidget(self.live_mode_status)
        self.live_status, self.live_error = label(), label()
        box.addWidget(self.live_status)
        box.addWidget(self.live_error)
        box.addWidget(label('LIVE diagnostics — scroll inside this panel to read all counters.'))
        self.health = QPlainTextEdit()
        self.health.setReadOnly(True)
        self.health.setAccessibleName('LIVE health and diagnostics (scrollable)')
        self.health.setMinimumHeight(230)
        self.health.setMaximumHeight(300)
        self.health.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        box.addWidget(self.health)
        box.addWidget(label(RESTORE_OUTPUT))
        return panel

    def _choose_live_mode(self, mode):
        # Native combo activation is a selection, not a toggle. Same-item
        # activation differs between platforms; Reset is an explicit action.
        if (self.state is None or self.state.source != 'system' or self.closing
                or self._stop_requested or self.busy not in (None, 'live_mode')):
            return False
        selected = self._pending_live_mode or self.state.live_mode
        if mode == selected:
            return False
        self._pending_live_mode = mode
        self._mode_requests.append(mode)
        self._live_mode_error = ''
        self._dispatch_live_mode()
        self.apply_state()
        return True

    def _dispatch_live_mode(self):
        # Only one command crosses the existing bounded worker queue at once.
        # Further meaningful native activations stay ordered on the GUI thread.
        if not self.busy and self._mode_requests and not self.closing:
            self._mode_inflight = self._mode_requests.popleft()
            self.submit('live_mode', self._mode_inflight)

    def _request_live_stop(self):
        # Stop/Close take priority over mode requests not yet dispatched. They
        # still wait for the owning worker; never close audio on the GUI thread.
        self._mode_requests.clear()
        self._pending_live_mode = self._mode_inflight
        self._stop_requested = True
        if not self.busy:
            self._stop_requested = False
            self.submit('stop')
        self.apply_state()

    def _apply_volume(self):
        return self.submit('volume', self.monitor_volume.value())

    def _toggle_mute(self):
        if self.state is None:
            return False
        if self.state.monitor_volume:
            self._last_nonzero_volume = self.state.monitor_volume
            target = 0
        else:
            target = getattr(self, '_last_nonzero_volume', 100)
        return self.submit('volume', target)

    def choose_file(self):
        if not self.open_file.isEnabled():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Open WAV file', '', 'WAV audio (*.wav *.WAV)')
        if path:
            self.submit('load', path)

    def _prepare_research(self):
        if not self.apply_research.isEnabled():
            return False
        return self.submit('research', self.research_mode.currentData(),
                           self.research_intensity.value() * 5)

    def submit(self, action, *args):
        if self.busy or self.closed_cleanly:
            return False
        self.busy = action
        self.started = time.monotonic()
        self.global_error.setText('')
        self.cleanup_error = ''
        self.file_error.setText('')
        self.live_error.setText('')
        self.activity.setText({'load': 'Loading audio and preparing modes…', 'start': 'Starting LIVE; validating devices and routing…',
                               'stop': 'LIVE stopping; releasing audio…', 'shutdown': 'Stopping audio and releasing resources…'}.get(action, 'Working…'))
        self.worker.submit(action, *args)
        self.apply_state()
        return True

    def drain_events(self):
        while True:
            try:
                kind, value = self.worker.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'state':
                sequence, state = value
                if sequence > self._state_sequence:
                    self._state_sequence, self.state = sequence, state
            elif kind == 'done':
                self.busy = None
                if value == 'live_mode':
                    self._mode_inflight = None
                    if not self._mode_requests:
                        self._pending_live_mode = None
                self.activity.setText('Audio session ready.')
            elif kind == 'message':
                self.activity.setText(value)
            elif kind == 'error':
                action, message = value
                target = self.file_error if action in ('load', 'file', 'file_output', 'poll', 'research', 'cancel_research') else self.live_error
                target.setText('Action required: ' + message)
                if action == 'live_mode':
                    self._live_mode_error = message
                    self._mode_requests.clear()
                    self._pending_live_mode = None
                    # A rejection explicitly reconciles to committed state.
                    self.live_mode_choice.hidePopup()
                if action == 'shutdown':
                    self.closing = False
                    self.cleanup_error = 'Cleanup is incomplete; the session remains owned by this window. Retry Close after the audio worker stops. ' + message
                    self.global_error.setText(self.cleanup_error)
            elif kind == 'unavailable':
                self.busy = None
                self.failed_initialize = True
                self.result_code = 1
                self.global_error.setText(value)
            elif kind == 'worker_failed':
                self.worker_failed = True
                self.closing = False
                self.busy = 'failed'
                self.cleanup_error = value + ' The window retains ownership. Use Close to retry cleanup.'
                self.global_error.setText(self.cleanup_error)
            elif kind == 'fatal_closed':
                print(value, file=sys.stderr)
                self.result_code = 1
                self.closed_cleanly = True
                self.timer.stop()
                self.close()
                return
            elif kind == 'closed':
                self.closed_cleanly = True
                self.timer.stop()
                self.close()
                return
        if self.busy and not self.worker_failed and time.monotonic() - self.started > 10:
            self.global_error.setText('Audio operation is taking longer than expected. The window remains responsive; Close will request cleanup after it returns. Do not launch another audio session.')
        self.apply_state()
        if self.closing and not self.busy and not self.failed_initialize:
            self.submit('shutdown')
        elif self._stop_requested and not self.busy:
            self._stop_requested = False
            self.submit('stop')
        else:
            self._dispatch_live_mode()

    @staticmethod
    def _choices(combo, choices, selected):
        # Preserve an uncommitted user choice across periodic state updates.
        old = combo.currentData()
        existing = tuple(combo.itemData(i) for i in range(combo.count()))
        committed_changed = getattr(combo, '_committed_choice', None) != selected
        if existing == (None, *choices) and not committed_changed:
            return
        combo._committed_choice = selected
        combo.clear()
        combo.addItem('Select a device…', None)
        for device in choices:
            combo.addItem(device.name, device)
        candidate = selected if committed_changed else old if old in choices else selected
        for i in range(combo.count()):
            if candidate == combo.itemData(i):
                combo.setCurrentIndex(i)
                break

    def _update_health(self, value):
        # LIVE metrics refresh continuously. setPlainText() resets the viewport
        # unless we restore it, making the lower counters effectively unreadable.
        old_text = self.health.toPlainText()
        if value == old_text:
            return
        scroll = self.health.verticalScrollBar()
        old_position, old_maximum = scroll.value(), scroll.maximum()
        follow_tail = bool(old_text) and old_position >= old_maximum - 1
        self.health.setPlainText(value)
        if follow_tail:
            scroll.setValue(scroll.maximum())
        else:
            scroll.setValue(min(old_position, scroll.maximum()))

    def apply_state(self):
        s = self.state
        available = s is not None and not self.busy and not self.closing
        for button in (self.open_file, self.play, self.pause, self.stop_file, self.start_live, self.stop_live,
                       self.apply_devices, self.apply_output, self.refresh, self.recheck, self.settings,
                       self.apply_volume, self.mute_volume, self.apply_research, self.cancel_research):
            button.setEnabled(bool(available))
        for combo in (self.capture, self.output, self.file_output, self.rate):
            combo.setEnabled(bool(available and s.can_configure))
        self.monitor_volume.setEnabled(bool(available))
        self.research_mode.setEnabled(bool(available and s.can_play))
        self.research_intensity.setEnabled(bool(available and s.can_play))
        self.apply_research.setEnabled(bool(available and s.can_play))
        self.cancel_research.setEnabled(bool(available and s.research_pending))
        for button in self.file_modes.values():
            button.setEnabled(False)
        # Set the final enabled state once. Temporarily disabling a combo on
        # every health tick dismisses its native popup before activation.
        mode_available = bool(s and s.source == 'system' and not self.closing
                              and not self._stop_requested
                              and self.busy in (None, 'live_mode'))
        self.live_mode_choice.setEnabled(mode_available)
        self.reset_live_mode.setEnabled(mode_available)
        if s is None:
            return
        self._choices(self.capture, s.captures, s.selected_capture)
        self._choices(self.output, s.outputs, s.selected_output)
        self._choices(self.file_output, s.outputs, s.selected_output)
        if not self.rate.hasFocus():
            # Do not overwrite a pending sample-rate choice before Apply.
            if not hasattr(self, '_rate_initialized'):
                self.rate.setCurrentIndex(self.rate.findData(s.rate))
                self._rate_initialized = True
        self.filename.setText(s.file_name or 'No file selected')
        if not getattr(self, '_research_initialized', False):
            if s.research_active:
                self.research_mode.setCurrentIndex(self.research_mode.findData(s.research_mode))
                self.research_intensity.setValue(s.research_intensity // 5)
            self._research_initialized = True
        active = (f'Active: {s.research_mode.title()} Remastered — {s.research_intensity}%'
                  if s.research_active else 'Active: ' + s.file_mode.title())
        self.research_status.setText(active + '\n' + s.research_status)
        self.research_summary.setText(s.research_summary)
        self.file_status.setText(s.preparation if s.file_state.value == 'File preparation in progress' else
                                 ('Open an audio file to begin' if not s.duration else s.file_state.value))
        if self.cleanup_error:
            self.global_error.setText(self.cleanup_error)
        elif s.error:
            self.global_error.setText('Action required: ' + s.error)
        self.position.setText(f'{s.position:.2f} / {s.duration:.2f} seconds')
        self.progress.setValue(round(1000 * s.position / s.duration) if s.duration else 0)
        self.open_file.setEnabled(bool(available and s.can_prepare))
        self.play.setEnabled(bool(available and s.can_play and s.file_state.value != 'File playing'))
        self.pause.setEnabled(bool(available and s.file_state.value == 'File playing'))
        self.stop_file.setEnabled(bool(available and s.can_play))
        self.apply_output.setEnabled(bool(available and s.can_configure and self.file_output.currentData()))
        self.apply_devices.setEnabled(bool(available and s.can_configure and self.capture.currentData() and self.output.currentData()))
        dirty_devices = (self.capture.currentData() != s.selected_capture or
                         self.output.currentData() != s.selected_output or self.rate.currentData() != s.rate)
        self.start_live.setEnabled(bool(available and s.can_start and not dirty_devices))
        self.stop_live.setEnabled(bool(not self.closing and self.busy in (None, 'live_mode')
                                       and (s.live_active or s.live_state.value == 'Fatal audio failure')))
        # Manual rescans can block in native device enumeration, too.
        self.refresh.setEnabled(bool(available and not s.stream_active))
        self.recheck.setEnabled(bool(available and not s.stream_active))
        for mode, button in self.file_modes.items():
            button.setEnabled(bool(available and s.can_play))
            button.setChecked(('original' if mode == 'bypass' else mode) == s.file_mode)
        if not self.monitor_volume.isSliderDown() and not self.monitor_volume.hasFocus():
            if self.monitor_volume.value() != s.monitor_volume:
                self.monitor_volume.setValue(s.monitor_volume)
        self.monitor_volume_status.setText(
            f'LIVE listening level: {s.monitor_volume}% '
            + ('(muted)' if s.monitor_volume == 0 else '(unity)' if s.monitor_volume == 100
               else '(ISLA output attenuation)'))
        self.mute_volume.setText('Unmute' if s.monitor_volume == 0 else 'Mute')
        # Choosing a LIVE mode keeps the existing DSP worker and stream.
        desired = self._pending_live_mode or s.live_mode
        if (not self.live_mode_choice.view().isVisible()
                and self.live_mode_choice.currentData() != desired):
            self.live_mode_choice.blockSignals(True)
            self.live_mode_choice.setCurrentIndex(self.live_mode_choice.findData(desired))
            self.live_mode_choice.blockSignals(False)
        chosen = s.live_mode.title()
        if self._pending_live_mode:
            self.live_mode_status.setText(
                f'Requested: {self._pending_live_mode.title()} — awaiting control worker; '
                f'confirmed: {chosen}; DSP worker: {s.live_applied_mode or "not running"}.')
        elif s.live_active:
            if s.live_applied_mode == s.live_mode:
                self.live_mode_status.setText(f'LIVE mode: {chosen} — selected by the DSP worker.')
            else:
                self.live_mode_status.setText(
                    f'LIVE mode: {chosen} — waiting for the next processed audio block; '
                    f'DSP worker: {s.live_applied_mode or "not yet observed"}.')
        else:
            self.live_mode_status.setText(f'LIVE mode: {chosen} — selected for the next start.')
        self.routing.setText(f"{'LIVE routing ready' if s.routing_ready else 'LIVE is not ready'}\nCurrent macOS output: {s.system_output}\nRequired macOS output: BlackHole 2ch\nISLA Capture: {s.capture}\nISLA Physical Playback: {s.output}")
        self.next_action.setText(s.routing_message + ('\nNext action: ' + MANUAL_SETTINGS + ' Return to ISLA and click Recheck Audio Routing.' if not s.routing_ready else
                                '\nNext action: Apply LIVE Devices / Select LIVE Source.' if s.source != 'system' or dirty_devices else ''))
        self.live_status.setText('LIVE stopping' if self.busy in ('stop', 'shutdown') else s.live_state.value)
        mode_error = 'Mode change rejected: ' + self._live_mode_error if self._live_mode_error else ''
        if s.live_failure_reason:
            stage = 'LIVE safety event (monitor stopping)' if s.live_active else 'LIVE stopped safely'
            self.live_error.setText(f'{stage}: {s.live_failure_reason}' + ('\n' + mode_error if mode_error else ''))
        elif mode_error:
            self.live_error.setText(mode_error)
        elif not s.error:
            # Do not clear command errors from the event handler until the
            # backend returns to a healthy state.
            self.live_error.setText('')
        if s.file_warning:
            self.file_error.setText(s.file_warning)
        self._update_health(s.live_health)

    def closeEvent(self, event):
        if self.closed_cleanly or self.failed_initialize:
            self.timer.stop()
            event.accept()
            return
        event.ignore()
        if self.worker_failed:
            if self.worker.retry_cleanup():
                self.worker_failed = False
                self.busy = 'shutdown'
                self.started = time.monotonic()
            return
        self.closing = True
        self._mode_requests.clear()
        self._pending_live_mode = self._mode_inflight
        self.activity.setText('Closing: waiting for the current operation, then stopping all audio…')
        self.apply_state()
        if not self.busy:
            self.submit('shutdown')


def launch(controller=None):
    # A modal ownership handoff requires this synchronous event loop. Refuse an
    # embedding application's existing loop instead of creating nested owners.
    global _application
    existing = QApplication.instance()
    if existing is not None and existing is not _application:
        raise RuntimeError('An existing Qt application owns the event loop. Launch isla window in a separate shell session after stopping audio.')
    if _application is None:
        _application = AudioApplication([sys.argv[0]])
    app = _application
    previous = app.window
    if previous is not None and not (previous.closed_cleanly or previous.failed_initialize):
        raise RuntimeError('The previous control window still owns its session. Close it before reopening.')
    app.setApplicationName('ISLA')
    worker = CommandWorker(controller)
    window = ControlWindow(worker)
    app.window = window
    worker.start()
    window.show()
    app.exec()
    # Normal window closure only occurs after worker-confirmed resource release.
    if not window.closed_cleanly and not window.failed_initialize:
        raise RuntimeError('Window event loop ended before audio cleanup; exit this process before starting another session.')
    return window.result_code
