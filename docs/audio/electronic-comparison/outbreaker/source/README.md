# Outbreaker — preserved original MP3

Music: **Outbreaker by Hinkik**. [Artist's original upload](https://www.newgrounds.com/audio/listen/681530).
License: **[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)**.

The original downloaded MP3 exceeds the per-request upload limit. These two
binary parts preserve all **13,161,112 original bytes**, including metadata:

- [outbreaker.mp3.part1](outbreaker.mp3.part1) — first 8,000,000 bytes.
- [outbreaker.mp3.part2](outbreaker.mp3.part2) — remaining 5,161,112 bytes.

The renderer joins them in memory automatically. To reconstruct a playable
original manually, run from this directory:

```bash
cat outbreaker.mp3.part1 outbreaker.mp3.part2 > outbreaker.mp3
```

The reconstructed original's SHA-256 must be:

`1049fbeeaf7919bec6d50219f525681aa4b75a0f8827a4ce13059623cbcde4ab`

This packaging makes no audio or metadata changes. The directly playable
24-second comparison files are in the parent directory. No artist endorsement
is implied.
