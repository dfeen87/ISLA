"""
ISLA
Smooth audio notes with phase-aligned transitions.

This engine mirrors the deterministic architecture of AeroCam:
Analyzer → Smoother → Harmonic Blender → Output.

MIT License
"""

import soundfile as sf
from isla.analyzer import NoteAnalyzer
from isla.smoother import PhaseSmoother
from isla.harmonics import HarmonicBlender


class IslaMusicEngine:
    """
    Static-style engine inspired by AeroCam's main.cpp.
    Modules are initialized once, mirroring embedded-style determinism.
    """

    def __init__(self, mode="velvet"):
        self.mode = mode
        self.analyzer = NoteAnalyzer()
        self.smoother = PhaseSmoother(mode=mode)
        self.harmonics = HarmonicBlender()

    def smooth_file(self, input_path, output_path):
        """
        Process audio from input_path to output_path.
        Supports both string file paths and file-like objects (e.g. io.BytesIO).
        """
        # Load audio
        audio, sr = sf.read(input_path)

        # Step 1: Detect note boundaries
        boundaries = self.analyzer.detect_boundaries(audio, sr)

        # Step 2: Apply smoothing per boundary region
        softened = self.smoother.apply(audio, boundaries, sr)

        # Step 3: Blend harmonics for gradual transitions
        final_output = self.harmonics.blend(softened, sr)

        # Step 4: Save output
        # If output_path is a file-like object without a format specified, default to WAV format
        if hasattr(output_path, "write"):
            sf.write(output_path, final_output, sr, format='WAV')
        else:
            sf.write(output_path, final_output, sr)

        print(f"[ISLA] Mode '{self.mode}' applied.")
        if hasattr(output_path, "name"):
            print(f"Output saved to {output_path.name}")
        elif isinstance(output_path, str):
            print(f"Output saved to {output_path}")
        else:
            print(f"Output saved to memory buffer.")


PhasedMusicEngine = IslaMusicEngine  # Backward-compatible alias.


if __name__ == "__main__":
    engine = IslaMusicEngine(mode="velvet")
    engine.smooth_file("input.wav", "output_smooth.wav")
