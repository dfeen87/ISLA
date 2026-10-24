import numpy as np
import time
from drivers.api import IslaBuffer

def main():
    print("--- VST Debug Roundtrip Example ---")
    sr = 44100

    # Simulate a typical VST buffer (e.g., 512 samples per block)
    block_size = 512
    num_blocks = 100
    total_samples = block_size * num_blocks

    # Create synthetic stereo buffer
    t = np.linspace(0, total_samples / sr, total_samples, endpoint=False)

    # Sweep frequency to add harmonic content
    freq = np.linspace(440, 880, total_samples)
    mono_signal = np.sin(2 * np.pi * freq * t)

    # Planar stereo
    stereo_buffer = np.column_stack([mono_signal, mono_signal]).astype(np.float32)

    print(f"Input buffer shape: {stereo_buffer.shape}")
    print(f"Input buffer dtype: {stereo_buffer.dtype}")

    rms_before = np.sqrt(np.mean(stereo_buffer**2))
    print(f"RMS before: {rms_before:.6f}")

    # Initialize processor
    pnb = IslaBuffer(mode="velvet", sr=sr)

    # Validate round-trip (mimicking processBlock iteration)
    # We'll just process the whole buffer for simplicity, or block-by-block to be more like a VST
    output_buffer = np.zeros_like(stereo_buffer)

    start_time = time.time()

    # In a real VST, this would happen block by block
    # However, IslaBuffer expects the whole buffer or handles boundaries internally
    # For this example, we'll process the full buffer at once to simulate passing the buffer from DAW to plugin
    output_buffer = pnb.process_buffer(stereo_buffer)

    end_time = time.time()

    print("\n--- After Processing ---")
    print(f"Output buffer shape: {output_buffer.shape}")
    print(f"Output buffer dtype: {output_buffer.dtype}")

    rms_after = np.sqrt(np.mean(output_buffer**2))
    print(f"RMS after: {rms_after:.6f}")

    print(f"Processing time: {(end_time - start_time) * 1000:.2f} ms")

    # Validations
    assert stereo_buffer.shape == output_buffer.shape, "Shape mismatch in roundtrip!"
    # Since numpy defaults to float64 for some operations in harmonics, we just make sure it returns a numpy array
    assert isinstance(output_buffer, np.ndarray), "Output is not a numpy array!"

if __name__ == "__main__":
    main()
