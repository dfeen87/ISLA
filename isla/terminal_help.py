"""Plain-text, width-aware help. Rendering never scans hardware or changes audio."""
from __future__ import annotations

import shutil
import textwrap
import unicodedata

LIVE = (
    ('source system', 'Select system audio; use your Mac app to play music.'),
    ('monitor start', 'Start LIVE when stopped (default 48000 Hz).'),
    ('monitor stop', 'Stop LIVE and release audio devices.'),
    ('bypass', 'Original input within the existing monitor.'),
    ('mode velvet', 'Select Velvet processing.'),
    ('mode legato', 'Select Legato processing.'),
    ('mode melt', 'Select Melt processing.'),
    ('engine remastered [0-100]', 'LIVE research engine; permitted depth in 5% steps, not volume.'),
    ('engine production', 'Use the original LIVE harmonic profiles.'),
    ('status', 'Show full LIVE diagnostics and recovery counters.'),
)
FILE = (
    ('source file', 'Select ALIVE file playback; stops LIVE.'),
    ('load <path>', 'Prepare local audio; missing bare filenames search this computer.'),
    ('play', 'Start or resume the prepared file.'),
    ('pause', 'Pause at the current position.'),
    ('stop', 'Stop the file and reset to the beginning.'),
    ('mode <name>', 'Select velvet, legato, or melt.'),
    ('bypass', 'Select the original decoded file.'),
)
DEVICES = (
    ('setup audio', 'Guided BlackHole capture and physical stereo output setup.'),
    ('devices', 'List audio endpoints and channel counts.'),
    ('input [name|id]', 'No argument: numbered LIVE capture picker.'),
    ('output [name|id]', 'No argument: numbered LIVE output picker.'),
    ('cancel', 'Leave an active picker; preserve previous selections.'),
)
OTHER = (
    ('help live', 'LIVE workflow and next steps.'),
    ('help file', 'ALIVE local audio playback workflow.'),
    ('help devices', 'BlackHole and physical output setup.'),
    ('help modes', 'Processing selection and Original / Bypass.'),
    ('help troubleshoot', 'Common mistakes and recovery.'),
    ('status', 'Detailed current state and telemetry.'),
    ('window', 'Open graphical controls; close to return here.'),
    ('help / ?', 'Show this command center.'),
    ('exit', 'Stop audio, release resources, return to the shell.'),
)
TOPIC_ALIASES = {'alive': 'file', 'system': 'live', 'device': 'devices',
                 'mode': 'modes', 'troubleshooting': 'troubleshoot', '?': ''}
TOPICS = ('live', 'file', 'devices', 'modes', 'troubleshoot')


def mode_name(mode):
    return 'Original / Bypass' if mode in ('original', 'bypass') else mode.title()


def next_step(controller):
    c = controller
    if c._setup_stage:
        return 'Choose a listed number or exact name, or cancel. monitor stop and exit remain available.'
    if c.live.running:
        if c.live.halt.is_set():
            return 'LIVE is stopping. Use monitor stop, then status before restarting.'
        return 'LIVE is running. Choose mode velvet, mode legato, mode melt, bypass, status, or monitor stop.'
    if c.source == 'system':
        if not c.output:
            return 'Run setup audio, or input then output and select listed numbers; then monitor start.'
        return 'Check macOS output is BlackHole 2ch and ISLA output is physical; then monitor start. See help devices.'
    if not c.player.buffers:
        return 'ALIVE: load "example.wav", check status, then play. For system audio: source system; setup audio.'
    return 'ALIVE: play, pause, stop, mode velvet|legato|melt, or bypass. status shows file progress.'


def _ascii(value):
    # Device/file names may contain Unicode or control characters. Keep borders
    # aligned and plain captures safe without emitting ANSI or terminal control.
    normalized = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'replace').decode('ascii')
    return ''.join(char if 32 <= ord(char) < 127 else ' ' for char in normalized)


def render_help(controller, topic='', *, width=None):
    topic = TOPIC_ALIASES.get(topic.casefold(), topic.casefold())
    if topic and topic not in TOPICS:
        return ('Unknown help topic. Choose: help live, help file, help devices, '
                'help modes, help troubleshoot; help or ? shows the command center.')
    width = max(12, min(width if width is not None else shutil.get_terminal_size((80, 24)).columns, 88))
    inner = width - 4
    lines = ['+' + '=' * (width - 2) + '+']

    def row(text='', *, center=False):
        for part in textwrap.wrap(_ascii(text), inner, break_long_words=True, break_on_hyphens=False) or ['']:
            lines.append('| ' + (part.center(inner) if center else part.ljust(inner)) + ' |')

    def section(title, commands=(), paragraphs=()):
        lines.append('+' + '-' * (width - 2) + '+')
        row(title)
        row()
        for command, description in commands:
            if width >= 70:
                # Continuation lines align with descriptions, not commands.
                parts = textwrap.wrap(_ascii(description), inner - 25)
                row(command.ljust(23) + '  ' + parts[0])
                for part in parts[1:]:
                    lines.append('| ' + (' ' * 25 + part).ljust(inner) + ' |')
            else:
                row(command)
                row('  ' + description)
        for paragraph in paragraphs:
            row(paragraph)

    c = controller
    row('I S L A', center=True)
    row('AUDIO CONTROL COMMAND CENTER', center=True)
    row('CONTEXT : ' + ('LIVE SYSTEM AUDIO' if c.source == 'system' else 'ALIVE FILE PLAYBACK'))
    row('SOURCE  : ' + ('SYSTEM AUDIO' if c.source == 'system' else 'LOCAL AUDIO FILE'))
    row('MONITOR : ' + ('RUNNING' if c.live.running else c.live.state.upper()))
    row('MODE    : ' + mode_name(c.live.mode if c.source == 'system' else c.player.mode).upper())
    config = c.live.config if c.live.running else None
    row('INPUT   : ' + (config.input_name if config else c.capture))
    row('OUTPUT  : ' + (config.output_name if config else c.output or
                        ('Not selected - run setup audio' if c.source == 'system' else 'System default (ALIVE)')))
    if c.source == 'file':
        row('FILE    : ' + str(c.path or (c.job.path if c.job else 'Not loaded')))
        row('PLAYER  : ' + c.player.state.upper())
    if c._setup_stage:
        section('DEVICE PICKER ACTIVE', paragraphs=(
            'Help does not select a device. Enter a listed number or exact name; cancel preserves routing.',))

    if not topic:
        primary, secondary = ((('LIVE AUDIO', LIVE), ('ALIVE FILE', FILE)) if c.source == 'system'
                              else (('ALIVE FILE', FILE), ('LIVE AUDIO', LIVE)))
        section(*primary)
        section(*secondary)
        section('DEVICE SETUP - STOP AUDIO FIRST', DEVICES)
        section('HELP AND SESSION', OTHER)
        section('EXAMPLES / TROUBLESHOOTING', paragraphs=(
            'LIVE: source system -> setup audio -> monitor start -> mode velvet -> bypass -> monitor stop',
            'ALIVE: source file -> load "example.wav" -> play -> pause -> stop',
            'play is for local audio files. LIVE captures ongoing Mac application audio. See help troubleshoot.'))
    elif topic == 'live':
        section('LIVE AUDIO', LIVE, (
            'EXAMPLE: source system -> setup audio -> monitor start -> mode velvet -> bypass -> monitor stop',
            'LIVE captures ongoing Mac application audio; start music in that app. play is only for ALIVE local audio files.',
            'monitor start [44100|48000] selects the rate when stopped; omit brackets when typing. An active start is idempotent.',
            'Bypass keeps monitoring active. Stop LIVE before changing devices.'))
    elif topic == 'file':
        section('ALIVE FILE', FILE, (
            'EXAMPLE: source file -> load "example.wav" -> status -> play -> pause -> stop',
            'On macOS, load DRM-free purchased M4A / AAC or Apple Lossless as well as WAV. Protected Apple Music downloads cannot be imported.',
            'ALIVE uses a prepared local audio file and can use the default output without BlackHole. output <name|id> changes output while stopped.',))
    elif topic == 'devices':
        section('DEVICE SETUP - STOP AUDIO FIRST', DEVICES, (
            'EXAMPLE: monitor stop -> source system -> input -> listed number -> output -> listed number -> monitor start',
            'The pickers accept numbers/exact names only while prompted. Existing input 0 and output "Exact device name" syntax remains available.',
            'macOS Sound Output must be standalone BlackHole 2ch; ISLA output must be verified physical stereo speakers/headphones. Aggregate and Multi-Output devices are excluded.',
            'In Audio MIDI Setup, BlackHole capture uses 0 dB unity (1.0). Start physical listening volume low; never blindly set speakers/headphones to 100%. Lower macOS alert volume separately.',
            'ISLA does not change macOS routing or permissions. After LIVE stops, restore normal macOS output manually. See README screenshots.'))
    elif topic == 'modes':
        section('PROCESSING MODES', (
            ('bypass', 'Original / unprocessed audio in the current source.'),
            ('mode velvet', 'Velvet harmonic profile.'),
            ('mode legato', 'Legato harmonic profile.'),
            ('mode melt', 'Melt harmonic profile.'),
        ), ('LIVE applies mode requests on the next processed block, keeping the existing stream open. File modes use prepared buffers. Effects can be subtle; compare at similar loudness.',
            'Window: choose an effect in Step 4. Re-selecting it is idempotent; use Reset to Original or choose Original / Bypass. Requested, confirmed and DSP-worker state are shown separately.'))
    else:
        section('TROUBLESHOOTING', paragraphs=(
            'play during LIVE: monitoring may already be running. Use status; choose a mode or bypass. Do not start a second stream.',
            'Cannot change output: monitor stop -> output -> listed physical stereo device number -> check macOS routing -> monitor start. Active output is preserved.',
            'No sound: play music in the Mac app, check BlackHole and physical output routing, check safe physical/ISLA listening volume and mute, then status. See help devices.',
            'Unexpected stop: capture the exact status error and counters; reconnect/recheck devices while stopped. Do not bypass routing safeguards.',
            'Shell commands belong at the Mac %/$ prompt. At isla> use window; use exit before running python -m isla window in the shell.',
            'monitor stop releases LIVE. exit, Ctrl-C or Ctrl-D stops audio and releases resources. cancel leaves a device picker.'))
    section('NEXT', paragraphs=(next_step(c),))
    lines.append('+' + '=' * (width - 2) + '+')
    return '\n'.join(lines)
