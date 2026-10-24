"""Read-only macOS routing inspection. Never writes a system audio property."""
from __future__ import annotations

import ctypes as C
import sys

from isla.playback import AudioError


def fourcc(value):
    return int.from_bytes(value.encode("ascii"), "big")


class Address(C.Structure):
    _fields_ = [("selector", C.c_uint32), ("scope", C.c_uint32), ("element", C.c_uint32)]


class CoreAudioRouting:
    """Fail closed on unidentifiable, aggregate, virtual, or missing outputs.

    Resolve PortAudio names only when unique in Core Audio. Preserve native IDs
    during a session so a hot-plug/index reassignment cannot silently reroute it.
    """
    PHYSICAL = {"bltn", "usb ", "blue", "blea", "hdmi", "dprt", "pci ", "thun", "1394"}

    def __init__(self):
        if sys.platform != "darwin":
            raise AudioError("LIVE system capture currently requires macOS and BlackHole 2ch.")
        self.ca = C.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        self.cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self.ca.AudioObjectGetPropertyDataSize.argtypes = [C.c_uint32, C.POINTER(Address), C.c_uint32, C.c_void_p, C.POINTER(C.c_uint32)]
        self.ca.AudioObjectGetPropertyData.argtypes = [C.c_uint32, C.POINTER(Address), C.c_uint32, C.c_void_p, C.POINTER(C.c_uint32), C.c_void_p]
        self.cf.CFStringGetCString.argtypes = [C.c_void_p, C.c_void_p, C.c_long, C.c_uint32]
        self.cf.CFStringGetCString.restype = C.c_bool
        self.cf.CFRelease.argtypes = [C.c_void_p]

    def _read(self, device, selector, result):
        address = Address(fourcc(selector), fourcc("glob"), 0)
        size = C.c_uint32(C.sizeof(result))
        status = self.ca.AudioObjectGetPropertyData(device, C.byref(address), 0, None, C.byref(size), C.byref(result))
        if status:
            raise AudioError(f"Core Audio device/routing unavailable ({status}). Stop, reconnect, and retry.")
        return result

    def _name(self, device):
        ref = self._read(device, "lnam", C.c_void_p())
        try:
            buffer = C.create_string_buffer(4096)
            if not self.cf.CFStringGetCString(ref, buffer, len(buffer), 0x08000100):
                raise AudioError("Cannot identify Core Audio device name.")
            return buffer.value.decode("utf-8")
        finally:
            if ref.value:
                self.cf.CFRelease(ref)

    def _has_streams(self, device, scope):
        address = Address(fourcc("stm#"), fourcc(scope), 0)
        size = C.c_uint32()
        status = self.ca.AudioObjectGetPropertyDataSize(device, C.byref(address), 0, None, C.byref(size))
        if status:
            raise AudioError("Cannot inspect Core Audio channel direction.")
        return size.value > 0

    def snapshot(self):
        address = Address(fourcc("dev#"), fourcc("glob"), 0)
        size = C.c_uint32()
        if self.ca.AudioObjectGetPropertyDataSize(1, C.byref(address), 0, None, C.byref(size)):
            raise AudioError("Cannot enumerate Core Audio devices.")
        devices = self._read(1, "dev#", (C.c_uint32 * (size.value // 4))())
        entries = []
        for device in devices:
            transport = self._read(device, "tran", C.c_uint32()).value.to_bytes(4, "big").decode("ascii", errors="replace")
            entries.append({"id": device, "name": self._name(device), "transport": transport,
                            "alive": bool(self._read(device, "livn", C.c_uint32()).value),
                            "input": self._has_streams(device, "inpt"),
                            "output": self._has_streams(device, "outp")})
        return entries, self._read(1, "dOut", C.c_uint32()).value

    def validate(self, capture_name, output_name, expected=None):
        entries, default = self.snapshot()
        selected = []
        for name, direction in ((capture_name, "input"), (output_name, "output")):
            matches = [entry for entry in entries if entry["name"] == name and entry["alive"] and entry[direction]]
            if len(matches) != 1:
                raise AudioError(f"Device missing or ambiguous: {name}. Reconnect and select again.")
            selected.append(matches[0])
        capture, output = selected
        if capture["name"] != "BlackHole 2ch" or capture["transport"] != "virt":
            raise AudioError("Select the standalone BlackHole 2ch capture device.")
        if output["id"] == capture["id"] or output["transport"] not in self.PHYSICAL:
            raise AudioError("LIVE output must be physical speakers/headphones, never BlackHole, Aggregate, or Multi-Output.")
        if default != capture["id"]:
            raise AudioError("Single-path routing required: manually set macOS Sound > Output to BlackHole 2ch (not Multi-Output). Restore speakers/headphones after LIVE.")
        identity = (capture["id"], output["id"])
        if expected is not None and identity != expected:
            raise AudioError("Audio device identity changed. Stop and select devices again.")
        return identity
