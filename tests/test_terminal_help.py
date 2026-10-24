"""Console guidance and stream ownership with synthetic device/audio fixtures."""
import pytest

from test_control import make_session


def test_help_is_ascii_command_center_and_distinguishes_sources():
    c, *_ = make_session()
    try:
        text = c.execute('help')
        assert text.startswith('+===')
        assert 'AUDIO CONTROL COMMAND CENTER' in text and 'ALIVE FILE' in text
        assert text.isascii() and '\x1b' not in text
        c.execute('source system')
        text = c.execute('help live')
        assert 'LIVE AUDIO' in text and 'monitor start' in text
    finally:
        c.close()


def test_running_live_mistakes_are_actionable_without_reopening_stream():
    c, live, *_ = make_session()
    try:
        c.execute('source system')
        c.execute('output 1')
        c.execute('monitor start')
        stream = live.streams[0]
        assert 'already running' in c.execute('play')
        assert 'Current mode:' in c.execute('monitor start')
        with pytest.raises(ValueError, match='monitor stop'):
            c.execute('output')
        assert c.live.running and c.live.stream is stream and len(live.streams) == 1
    finally:
        c.close()


@pytest.mark.parametrize('width', [16, 32, 40, 60, 70, 80, 88, 200])
@pytest.mark.parametrize('topic', ['', 'live', 'file', 'devices', 'modes', 'troubleshoot'])
def test_help_width_ascii_and_complete_borders(width, topic):
    from isla.terminal_help import render_help
    c, *_ = make_session()
    try:
        c.output = 'Long headphones with Unicode café 🎵 and embedded\ncontrol\x1b[31m text ' * 3
        text = render_help(c, topic, width=width)
        assert text.isascii() and '\x1b' not in text
        assert all(len(line) == min(width, 88) for line in text.splitlines())
        assert all(line[0] in '+|' and line[-1] in '+|' for line in text.splitlines())
    finally:
        c.close()


def test_context_order_missing_output_and_actual_monitor_values(monkeypatch):
    c, live, *_ = make_session()
    try:
        file_help = c.execute('help')
        assert file_help.index('ALIVE FILE') < file_help.index('LIVE AUDIO')
        c.execute('source system')
        assert 'setup audio' in c.execute('help').split('| NEXT')[1]
        c.execute('output 1')
        c.execute('monitor start 44100')
        c.execute('mode legato')
        # Help is a read-only snapshot: hardware discovery is forbidden here.
        monkeypatch.setattr(c.player.backend, 'devices', lambda: pytest.fail('help enumerated hardware'))
        text = c.execute('help')
        assert text.index('LIVE AUDIO') < text.index('ALIVE FILE')
        assert 'RUNNING' in text and 'LEGATO' in text and 'Test speakers' in text
        assert 'BlackHole 2ch' in text
        assert c.execute('?') == text
        assert len(live.streams) == 1
    finally:
        c.close()


@pytest.mark.parametrize('alias,topic', [('alive','file'), ('system','live'), ('device','devices'),
                                        ('mode','modes'), ('troubleshooting','troubleshoot')])
def test_help_aliases_and_invalid_topics(alias, topic):
    c, *_ = make_session()
    try:
        assert c.execute('HELP ' + alias.upper()) == c.execute('help ' + topic)
        assert 'Unknown help topic' in c.execute('help imaginary')
        assert 'Usage: help' in c.execute('help live extra')
    finally:
        c.close()


@pytest.mark.parametrize('command', ['input', 'output', 'input 0', 'output 1', 'output "Test speakers"', 'setup audio'])
def test_device_changes_during_live_preserve_ownership(command):
    c, live, *_ = make_session()
    try:
        c.execute('source system')
        c.execute('output 1')
        c.execute('monitor start')
        stream = c.live.stream
        with pytest.raises(ValueError):
            c.execute(command)
        assert c.output == 'Test speakers' and c.capture == 'BlackHole 2ch'
        assert c._setup_stage is None
        assert c.live.stream is stream and stream.active and not stream.closed
        assert len(live.streams) == 1
    finally:
        c.close()


def test_running_commands_keep_stream_and_every_status_field(monkeypatch):
    c, live, *_ = make_session()
    try:
        c.execute('source system')
        c.execute('output 1')
        c.execute('monitor start')
        stream = c.live.stream
        # Neither mistaken play nor repeated start may even call start/configure.
        monkeypatch.setattr(c.live, 'start', lambda *a: pytest.fail('reopened LIVE'))
        for _ in range(3):
            assert 'local audio files' in c.execute('play')
            assert 'Current mode:' in c.execute('monitor start 44100')
            assert 'existing stream' in c.execute('bypass')
            assert c.live.mode == 'bypass' and c.live.stream is stream and c.live.running
        diagnostics = c.live.status()
        status = c.execute('status')
        assert status.startswith(diagnostics + '\nSelected input:')
        assert 'NEXT:' in status and 'Recovery attempts/completed/failed' in status
        assert len(live.streams) == 1 and c.live.config.rate == 48000
    finally:
        c.close()


def test_picker_help_topics_cancel_numeric_and_exact_selectors():
    c, *_ = make_session()
    try:
        c.execute('source system')
        for direction, number, name in [('input', '0', 'BlackHole 2ch'), ('output', '1', 'Test speakers')]:
            menu = c.execute(direction)
            assert '[' + number + ']' in menu
            assert 'DEVICE PICKER ACTIVE' in c.execute('help live')
            assert c._setup_stage == direction
            assert 'Unknown help topic' in c.execute('help wrong')
            assert c._setup_stage == direction
            assert 'canceled' in c.execute('cancel')
            c.execute(direction)
            assert name in c.execute(number)
            assert c._setup_stage is None
            assert name in c.execute(direction + ' "' + name + '"')
            assert name in c.execute(direction + ' ' + number)
        with pytest.raises(ValueError, match='Unknown command'):
            c.execute('1')
        c.execute('output')
        assert 'stopped' in c.execute('monitor stop').lower()
        assert c._setup_stage == 'output'
        assert 'Goodbye' in c.execute('exit') and c.closed
    finally:
        c.close()


def test_help_and_cleanup_available_despite_failed_file_preparation():
    from test_alive import PendingPreparation
    c, *_ = make_session()
    try:
        c.job = PendingPreparation('bad.wav')
        c.job.poll = lambda: (_ for _ in ()).throw(RuntimeError('preparation failed'))
        assert 'COMMAND CENTER' in c.execute('help')
        assert 'stopped' in c.execute('monitor stop').lower()
        assert 'Goodbye' in c.execute('exit')
    finally:
        c.close()
