# BEDROCK 1.0 Residual Risk Register

The following significant limitations were identified but excluded from the immediate repair scope to prevent uncontrolled architecture redesign.

## 1. Streaming DSP Discontinuities
**Risk:** When an audio stream is processed in independent small chunks, the lack of retained internal state (such as overlap buffers and phase memory from previous chunks) causes audible clicks at block boundaries.
**Evidence:** `test_harmonic_blender_streaming_continuity` demonstrates a maximum divergence nearing 1.0 when a pure sine wave is split into tiny blocks and blended, compared to a single large blend.
**Action Required:** Implement a stateful DSP interface (e.g., `process_block(block)`) that retains overlap tails and applies them to subsequent blocks.

## 2. Real-Time Violations in C++ / Python Bridge
**Risk:** `python_bridge.cpp` embeds `pybind11` calls directly inside the `process_audio` callback. This callback acquires the Global Interpreter Lock (GIL), allocates NumPy arrays dynamically on the heap, and runs Python bytecode. In a production DAW environment, this will immediately and repeatedly cause audio dropouts, glitches, and potential crashes.
**Evidence:** Source inspection of `python_bridge.cpp`.
**Action Required:** A profound architectural shift is needed if this plugin intends to be a real-time VST. Either:
1. Re-write the DSP engine entirely in C++.
2. Create an asynchronous lock-free ring buffer system where the audio callback only reads/writes raw samples, and a background thread processes them through Python.

## 3. High CPU Load from FFT Processing
**Risk:** Performing multiple overlapping FFT/IFFT pairs on every block across all channels (especially in stereo) creates a high and spiky CPU workload.
**Evidence:** The use of `np.fft` in Python.
**Action Required:** Future iterations must benchmark the exact CPU footprint of these FFTs if real-time functionality is eventually pursued.
