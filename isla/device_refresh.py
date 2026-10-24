"""Refresh PortAudio's device cache only under an idle session lease."""
import sys

from isla.playback import AudioError


def refresh_portaudio(controller):
    if controller.player.stream is not None or controller.live.running or controller.live.stream is not None:
        raise AudioError('Stop ALIVE and LIVE before refreshing the audio device cache.')
    sd = getattr(controller.player.backend, 'sd', None)
    if sd is None or getattr(sd,'__name__',None) != 'sounddevice' or sys.platform != 'darwin':
        return False
    # query_devices reads PortAudio's cached list on macOS. Reinitialization is
    # deliberately isolated here: sounddevice 0.5.x has no public rescan API.
    # No CoreAudio property/default/volume is written. All owned streams have
    # been released before touching this process-local PortAudio lifetime.
    terminate, initialize = getattr(sd,'_terminate',None),getattr(sd,'_initialize',None)
    if terminate is None or initialize is None:
        raise AudioError('Audio rescan unavailable; close ISLA and reopen after connecting the device.')
    owners = getattr(sd,'_initialized',1)
    if owners not in (0,1):
        raise AudioError('Audio library has another initialization owner; close ISLA before rescanning devices.')
    if owners:
        terminate()
    initialize()
    return True


def eligible_devices(native, portaudio):
    """Independent capture/output inventories; missing BlackHole cannot hide speakers."""
    from isla.coreaudio import CoreAudioRouting
    captures, outputs = [], []
    for device in portaudio:
        name = device['name']
        inputs = [n for n in native if n['name'] == name and n['alive'] and n['input']]
        outputs_native = [n for n in native if n['name'] == name and n['alive'] and n['output']]
        # Bluetooth may expose separate, equally named input/output objects.
        # Resolve uniqueness in the requested direction, never across both.
        input_unique = sum(d['name'] == name and d['max_input_channels'] > 0 for d in portaudio) == 1
        output_unique = sum(d['name'] == name and d['max_output_channels'] > 0 for d in portaudio) == 1
        if (name == 'BlackHole 2ch' and input_unique and len(inputs) == 1
                and inputs[0]['transport'] == 'virt' and device['max_input_channels'] == 2):
            captures.append(dict(device,native_id=inputs[0]['id'],transport=inputs[0]['transport']))
        if (name != 'BlackHole 2ch' and output_unique and len(outputs_native) == 1
                and outputs_native[0]['transport'] in CoreAudioRouting.PHYSICAL
                and device['max_output_channels'] >= 2):
            outputs.append(dict(device,native_id=outputs_native[0]['id'],transport=outputs_native[0]['transport']))
    return captures, outputs
