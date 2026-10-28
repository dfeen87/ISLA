# Automatic listening-output setup at ALIVE Play

Open a recording, wait for preparation, then press Play. On macOS the command
worker refreshes the verified physical output list and validates the recording's
actual rate/channel requirements before opening audio. An existing compatible
choice is retained; otherwise a unique compatible external output, or the sole
compatible physical output, is selected. Several suitable choices require a
selection in the ALIVE output menu followed by Play. A new explicit selection is
honored and a stale native identity is rejected.

Both output menus reflect the committed device. While ALIVE plays, the LIVE
setup button reads **Connected — ALIVE playing** and device changes are disabled.
Stop restores setup. The capture connection and macOS default route are advisory
for LIVE and never gate local-file playback. LIVE is not started automatically.
Portable ALIVE retains its existing backend/OS-default path when CoreAudio is
unavailable. Existing playback is never rescanned by a duplicate Play command.

A muted native Open File → Play check began with no selected output while the
Mac default was BlackHole. It selected Sony WH-CH720N, played a 44.1 kHz file,
synchronized both menus, disabled the setup controls and restored them after
Stop. LIVE remained inactive and the macOS route remained BlackHole. See
[native-auto-play-2026-10-27.json](native-auto-play-2026-10-27.json).

The two original macOS CI failures on PR #89 were the same fixed-delay switch
animation assertion: the speed state was already off, but the last visual frame
had not completed at 180 ms. The regression now waits for the animation's actual
Stopped state and deliberately uses a 350 ms animation, retaining exact endpoint
assertions. Workflow coverage and audio protections are unchanged.
