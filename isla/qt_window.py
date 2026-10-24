"""Qt Widgets presentation. All audio operations execute on one daemon worker.

The event thread consumes immutable snapshots only. It never enumerates devices,
prepares audio, waits on a worker or closes an audio stream. A stalled operation
leaves the window responsive with explicit diagnostics and retains the exclusive
session lease until cleanup completes; it never hands a busy engine to the CLI.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QGridLayout, QLabel, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
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
        self.thread = threading.Thread(target=self._run, name='isla-control', daemon=True)

    def start(self):
        self.thread.start()

    def submit(self, action, *args):
        self.commands.put_nowait((action, args))

    def _publish(self):
        self.events.put(('state', self.service.snapshot()))

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
        checked = time.monotonic()
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
                    self.service.poll()
                    if time.monotonic() - checked > 2:
                        self.service.refresh_devices()
                        checked = time.monotonic()
                else:
                    method = {'load': self.service.load_file, 'file': self.service.file_command,
                              'live_mode': self.service.live_mode, 'devices': self.service.select_devices,
                              'file_output': self.service.select_file_output,
                              'refresh': self.service.refresh_devices, 'start': self.service.start_live,
                              'stop': self.service.stop_live}[action]
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
        self.state = None
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
        for name, value in [('Original / Bypass', 'bypass'), ('Velvet', 'velvet'), ('Legato', 'legato'), ('Melt', 'melt')]:
            button = QPushButton(name)
            button.setCheckable(True)
            if source == 'file':
                command = 'bypass' if value == 'bypass' else 'mode ' + value
                button.clicked.connect(lambda checked=False, cmd=command: self.submit('file', cmd))
            else:
                button.clicked.connect(lambda checked=False, mode=value: self.submit('live_mode', mode))
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
        box.addWidget(label('Listening output (shared with LIVE)'))
        self.file_output = QComboBox()
        self.file_output.setAccessibleName('ALIVE physical listening output')
        box.addWidget(self.file_output)
        self.apply_output = QPushButton('Use Listening Output')
        self.apply_output.clicked.connect(lambda: self.submit('file_output', self.file_output.currentData()))
        box.addWidget(self.apply_output)
        box.addWidget(label('ALIVE can use the system default output without BlackHole. Physical output choices are offered when verified by macOS. Stop audio before changing devices.'))
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
        self.stop_live.clicked.connect(lambda: self.submit('stop'))
        row.addWidget(self.start_live)
        row.addWidget(self.stop_live)
        box.addLayout(row)
        self.live_modes = self._modes(box, 'live')
        self.live_status, self.live_error = label(), label()
        box.addWidget(self.live_status)
        box.addWidget(self.live_error)
        self.health = QPlainTextEdit()
        self.health.setReadOnly(True)
        self.health.setAccessibleName('LIVE health and diagnostics')
        self.health.setMaximumHeight(155)
        box.addWidget(self.health)
        box.addWidget(label(RESTORE_OUTPUT))
        return panel

    def choose_file(self):
        if not self.open_file.isEnabled():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Open WAV file', '', 'WAV audio (*.wav *.WAV)')
        if path:
            self.submit('load', path)

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
                self.state = value
            elif kind == 'done':
                self.busy = None
                self.activity.setText('Audio session ready.')
            elif kind == 'message':
                self.activity.setText(value)
            elif kind == 'error':
                action, message = value
                target = self.file_error if action in ('load', 'file', 'file_output', 'poll') else self.live_error
                target.setText('Action required: ' + message)
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
            self.global_error.setText('Audio operation is taking longer than expected. The window remains responsive; commands are locked until it returns. Close will request cleanup. Do not launch another audio session.')
        self.apply_state()
        if self.closing and not self.busy and not self.failed_initialize:
            self.submit('shutdown')

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

    def apply_state(self):
        s = self.state
        available = s is not None and not self.busy and not self.closing
        for button in (self.open_file, self.play, self.pause, self.stop_file, self.start_live, self.stop_live,
                       self.apply_devices, self.apply_output, self.refresh, self.recheck, self.settings):
            button.setEnabled(bool(available))
        for combo in (self.capture, self.output, self.file_output, self.rate):
            combo.setEnabled(bool(available and s.can_configure))
        for button in (*self.file_modes.values(), *self.live_modes.values()):
            button.setEnabled(False)
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
        self.stop_live.setEnabled(bool(available and (s.live_active or s.live_state.value == 'Fatal audio failure')))
        for mode, button in self.file_modes.items():
            button.setEnabled(bool(available and s.can_play))
            button.setChecked(('original' if mode == 'bypass' else mode) == s.file_mode)
        for mode, button in self.live_modes.items():
            button.setEnabled(bool(available and s.source == 'system'))
            button.setChecked(mode == s.live_mode)
        self.routing.setText(f"{'LIVE routing ready' if s.routing_ready else 'LIVE is not ready'}\nCurrent macOS output: {s.system_output}\nRequired macOS output: BlackHole 2ch\nISLA Capture: {s.capture}\nISLA Physical Playback: {s.output}")
        self.next_action.setText(s.routing_message + ('\nNext action: ' + MANUAL_SETTINGS + ' Return to ISLA and click Recheck Audio Routing.' if not s.routing_ready else
                                '\nNext action: Apply LIVE Devices / Select LIVE Source.' if s.source != 'system' or dirty_devices else ''))
        self.live_status.setText('LIVE stopping' if self.busy in ('stop', 'shutdown') else s.live_state.value)
        if s.file_warning:
            self.file_error.setText(s.file_warning)
        self.health.setPlainText(s.live_health)

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
