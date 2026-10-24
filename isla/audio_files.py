"""Local ALIVE decoding, including DRM-free Apple purchases on macOS."""
from pathlib import Path
import subprocess
import sys

import soundfile as sf

APPLE_AUDIO = {'.m4a', '.aac', '.mp4'}
PROTECTED_AUDIO = {'.m4p', '.movpkg'}
PROTECTED_MESSAGE = (
    'Protected Apple Music downloads cannot be imported into ALIVE. '
    'Download the DRM-free purchased AAC (.m4a) file from the iTunes Store '
    'in Music, then select that local file.'
)
AUDIO_FILE_FILTER = (
    'Audio files (*.wav *.WAV *.m4a *.M4A *.aac *.AAC *.mp4 *.MP4 '
    '*.mp3 *.MP3 *.flac *.FLAC *.aiff *.AIFF *.aif *.AIF *.ogg *.OGG);;'
    'All files (*)'
)


def inspect_audio(path):
    """Check ordinary headers; leave Apple decoding to the cancellable worker."""
    if Path(path).suffix.lower() in PROTECTED_AUDIO:
        raise ValueError(PROTECTED_MESSAGE)
    if not Path(path).is_file():
        raise ValueError(f'Audio file not found: {path}')
    try:
        return sf.info(str(path))
    except (RuntimeError, OSError) as exc:
        if Path(path).suffix.lower() in APPLE_AUDIO:
            if sys.platform == 'darwin':
                return None
            raise ValueError('AAC / Apple Lossless import requires macOS. '
                             'Export a DRM-free WAV, FLAC or AIFF file for this system.') from exc
        raise ValueError(f'Unsupported or invalid audio file: {path}') from exc


def decode_apple_audio(path, directory):
    """Make a float WAV for the frozen preparation worker, without resampling."""
    # afconvert ships with macOS and supports both AAC and ALAC in M4A.
    # No sample-rate/channel options: preserve both for the existing validator.
    decoded = Path(directory) / 'decoded.wav'
    try:
        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEF32',
                        str(path), str(decoded)], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return decoded
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('Unsupported or invalid audio file. Select a complete, '
                         'DRM-free purchased AAC (.m4a) or Apple Lossless file. '
                         'Protected Apple Music subscription downloads cannot be imported.') from exc
