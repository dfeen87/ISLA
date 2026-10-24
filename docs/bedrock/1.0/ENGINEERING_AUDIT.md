# BEDROCK 1.0 Engineering Audit

## Execution Summary
The BEDROCK 1.0 audit assessed the Phased-Music-Notes DSP engine with a focus on numerical audio integrity, deterministic bottom-up behavior, and software boundaries. The audit uncovered a critical mathematical flaw in the harmonic blender's overlap-add reconstruction scheme and identified severe real-time risks within the C++/Python plugin bridge.

## Prioritized Findings

### 1. `HarmonicBlender` Missing Overlap-Add Normalization
**Severity**: CRITICAL
**Status**: RESOLVED
**Description**: The overlap-add implementation for the Short-Time Fourier Transform (STFT) inside `HarmonicBlender` failed to apply per-sample gain normalization across overlapping windows. Consequently, the identity transformation (`HarmonicBlender(strength=0)`) produced heavily distorted outputs that grew and fell with the window envelope.
**Reproduction**: `tests/test_harmonics_adversarial.py::test_harmonic_blender_identity`
**Resolution**: The reconstruction was augmented with zero-padding on both boundaries to properly capture the edges. Additionally, we now square the synthesis window and accumulate it as an overlap-weight per frame, ultimately dividing the final audio buffer by this sum to ensure perfect signal normalization at all points.

### 2. Lack of Retained Context in Streaming DSP
**Severity**: HIGH
**Status**: NOT RESOLVED (Deferred to RESIDUAL RISKS)
**Description**: Chunking a continuous audio signal into smaller blocks results in discontinuities across block boundaries. Because the DSP modules lack internal retained state (e.g. historical buffers or phase context), `HarmonicBlender` processes each block blindly, generating independent windows that cannot be gaplessly spliced back together.
**Reproduction**: `tests/test_harmonics_adversarial.py::test_harmonic_blender_streaming_nonzero_strength`
**Resolution**: Documented as a fundamental architectural risk. Requires a deeper redesign of state-holding DSP nodes.

### 3. C++/Python Bridge Memory Allocation in Real-Time Path
**Severity**: CRITICAL
**Status**: NOT RESOLVED (Deferred to RESIDUAL RISKS)
**Description**: The JUCE VST integration defined in `drivers/vst/python_bridge.cpp` allocates memory (`py::array_t`) and invokes the global Python interpreter during the audio processing callback (`process_audio()`). This inherently violates real-time constraints and will cause audio dropouts in DAWs.
**Reproduction**: Inspection of `python_bridge.cpp` where GIL acquisition, exception handling, and NumPy heap allocation occur.
**Resolution**: Documented as an architectural limitation. Requires a complete bridge rewrite or a rewrite of the DSP in C++.

### 4. Dependency on Explicit VST2 Disable
**Severity**: LOW
**Status**: RESOLVED (Verified)
**Description**: The `CMakeLists.txt` appropriately sets `JUCE_BUILD_VST2 OFF` before the JUCE include, as per project requirements, guaranteeing that no VST2 artifact is inadvertently bundled.
**Resolution**: Confirmed via CMake inspection.

## Conclusion
The fundamental DSP integrity of single-buffer processing has been restored. However, the system cannot safely be considered "real-time capable" due to both streaming discontinuities and memory allocation within the C++ audio callback.
