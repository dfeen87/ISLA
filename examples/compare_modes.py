import io
import numpy as np
import soundfile as sf
from drivers.api import IslaBuffer

def compute_spectral_centroid(audio, sr):
    # Compute using NumPy FFT magnitude
    spectrum = np.fft.rfft(audio)
    mag = np.abs(spectrum)

    # Frequencies corresponding to the bins
    freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)

    # Compute centroid
    centroid = np.sum(freqs * mag) / (np.sum(mag) + 1e-9)
    return centroid

def main():
    print("--- Compare Modes Example ---")
    sr = 44100

    # Generate synthetic signal (sine -> discontinuity -> sine)
    t1 = np.linspace(0, 0.5, sr // 2, endpoint=False)
    sine1 = np.sin(2 * np.pi * 440 * t1)

    t2 = np.linspace(0, 0.5, sr // 2, endpoint=False)
    # High frequency to show the transition
    sine2 = np.sin(2 * np.pi * 2200 * t2)

    mono_signal = np.concatenate([sine1, sine2])
    # Make stereo
    signal = np.column_stack([mono_signal, mono_signal])

    print(f"Original signal length: {len(signal)} samples")

    centroids = {}

    modes = ["velvet", "legato", "melt"]
    for mode in modes:
        pnb = IslaBuffer(mode=mode, sr=sr)
        output = pnb.process_buffer(signal)

        # Use an in-memory buffer to simulate disk write
        out_buffer = io.BytesIO()
        sf.write(out_buffer, output, sr, format='WAV')
        print(f"Processed mode '{mode}' and wrote to memory buffer (size {out_buffer.getbuffer().nbytes} bytes)")

        # Calculate centroid of the first channel
        centroid = compute_spectral_centroid(output[:, 0], sr)
        centroids[mode] = centroid

    print("\nSpectral Centroid Comparison:")
    for mode in modes:
        print(f"  {mode.ljust(8)} : {centroids[mode]:.2f} Hz")

if __name__ == "__main__":
    main()
