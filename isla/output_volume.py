"""Explicit control of the selected physical output's native master volume.

Routing inspection and DSP remain unchanged. Only set_percent(), called after
a user's device-volume edit, writes the selected output's volume/mute property.
"""
from dataclasses import dataclass
import ctypes as C
import math

from isla.coreaudio import Address, fourcc
from isla.playback import AudioError


@dataclass(frozen=True)
class OutputVolume:
    percent: int | None = None
    available: bool = False
    muted: bool = False
    message: str = 'Select a listening device to check its volume.'


class CoreAudioOutputVolume:
    @staticmethod
    def _device(routing, choice):
        if choice is None or routing is None or not hasattr(routing, 'ca'):
            raise AudioError('Device volume is unavailable; use the controls on your listening device.')
        native, _ = routing.snapshot()
        device = next((d for d in native if (d['id'], d['name']) ==
                       (choice.native_id, choice.name)), None)
        if (device is None or not device['alive'] or not device['output']
                or device['transport'] not in routing.PHYSICAL):
            raise AudioError('The selected physical listening device changed. Refresh and select it again.')
        ca = routing.ca
        ca.AudioObjectHasProperty.argtypes = [C.c_uint32, C.POINTER(Address)]
        ca.AudioObjectHasProperty.restype = C.c_bool
        ca.AudioObjectIsPropertySettable.argtypes = [C.c_uint32, C.POINTER(Address), C.POINTER(C.c_bool)]
        ca.AudioObjectSetPropertyData.argtypes = [C.c_uint32, C.POINTER(Address), C.c_uint32,
                                                C.c_void_p, C.c_uint32, C.c_void_p]
        return ca, device['id']

    @staticmethod
    def _read(ca, identity, selector, cls):
        address = Address(fourcc(selector), fourcc('outp'), 0)
        if not ca.AudioObjectHasProperty(identity, C.byref(address)):
            return None
        value, size = cls(), C.c_uint32(C.sizeof(cls))
        status = ca.AudioObjectGetPropertyData(identity, C.byref(address), 0, None,
                                              C.byref(size), C.byref(value))
        if status:
            raise AudioError('Could not read the listening device volume. Refresh and retry.')
        return value.value

    @staticmethod
    def _writable(ca, identity, selector):
        address = Address(fourcc(selector), fourcc('outp'), 0)
        result = C.c_bool()
        status = ca.AudioObjectIsPropertySettable(identity, C.byref(address), C.byref(result))
        return not status and result.value

    def read(self, routing, choice):
        try:
            ca, identity = self._device(routing, choice)
            value = self._read(ca, identity, 'volm', C.c_float)
            if value is None:
                return OutputVolume(message='Use the volume controls on ' + choice.name + '.')
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise AudioError('The listening device returned an invalid volume level.')
            muted = bool(self._read(ca, identity, 'mute', C.c_uint32))
            available = self._writable(ca, identity, 'volm') and (
                not muted or self._writable(ca, identity, 'mute'))
            message = ('Use the volume controls on ' + choice.name + '.' if not available else
                choice.name + (' is muted. Move this slider to unmute.' if muted else
                ' — controls the actual listening device. Mac volume keys adjust BlackHole during LIVE.'))
            return OutputVolume(round(value * 100), available, muted,
                                message)
        except Exception as exc:
            return OutputVolume(message=str(exc))

    def set_percent(self, routing, choice, percent):
        if type(percent) is not int or not 0 <= percent <= 100:
            raise AudioError('Device volume must be a whole number from 0 to 100%.')
        ca, identity = self._device(routing, choice)
        if (self._read(ca, identity, 'volm', C.c_float) is None
                or not self._writable(ca, identity, 'volm')):
            raise AudioError('Use the volume controls on ' + choice.name + '.')
        muted = bool(self._read(ca, identity, 'mute', C.c_uint32))
        if percent and muted and not self._writable(ca, identity, 'mute'):
            raise AudioError('Unmute ' + choice.name + ' using its own controls first.')
        changes = [('volm', C.c_float(percent / 100))]
        if percent and muted:
            changes.append(('mute', C.c_uint32(0)))
        for selector, value in changes:
            address = Address(fourcc(selector), fourcc('outp'), 0)
            status = ca.AudioObjectSetPropertyData(identity, C.byref(address), 0, None,
                                                  C.sizeof(value), C.byref(value))
            if status:
                raise AudioError('Could not update the listening device volume. Refresh and retry.')
        return self.read(routing, choice)
