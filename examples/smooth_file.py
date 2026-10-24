import io
import numpy as np
import soundfile as sf
import time
from isla import SmoothPhase

def main():
    # 1. Generate synthetic WAV in memory
    sr = 44100
    t1 = np.linspace(0, 0.5, sr // 2, endpoint=False)
    sine1 = np.sin(2 * np.pi * 440 * t1)
    t2 = np.linspace(0, 0.5, sr // 2, endpoint=False)
    sine2 = np.sin(2 * np.pi * 880 * t2)

    signal = np.concatenate([sine1, sine2])

    # Use BytesIO instead of writing to disk
    input_wav_buffer = io.BytesIO()
    sf.write(input_wav_buffer, signal, sr, format='WAV')
    input_wav_buffer.seek(0)

    output_wav_buffer = io.BytesIO()

    print("--- SmoothPhase DSL Example ---")
    print(f"Generated synthetic input in memory buffer ({len(signal)} samples)")

    # 2. Use SmoothPhase DSL directly with the BytesIO buffers
    start_time = time.time()

    sp = SmoothPhase(mode="velvet")
    sp.smooth_file(input_wav_buffer, output_wav_buffer)

    end_time = time.time()

    output_wav_buffer.seek(0)
    # Just to verify, we can read back from the output buffer
    out_audio, out_sr = sf.read(output_wav_buffer)

    print(f"Mode applied: {sp.mode}")
    print(f"Output generated in memory buffer ({len(out_audio)} samples)")
    print(f"Processing time: {(end_time - start_time) * 1000:.2f} ms")

if __name__ == "__main__":
    main()
