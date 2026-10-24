// python_bridge.cpp
// Experimental C++/Python bridge for ISLA (not validated as real-time safe)

#include <pybind11/embed.h>
#include <pybind11/numpy.h>

namespace py = pybind11;

static bool g_python_initialized = false;
static py::object g_engine;

// -------------------------------------------------------------
// Initialize Python + IslaBuffer
// -------------------------------------------------------------
void init_python(int sampleRate, const std::string& mode = "velvet")
{
    if (g_python_initialized)
        return;

    py::initialize_interpreter();

    try {
        // Import the API driver
        py::module api = py::module::import("drivers.api");

        // Get the buffer-based DSP class
        py::object BufferClass = api.attr("IslaBuffer");

        // Instantiate engine with mode + sample rate
        g_engine = BufferClass(mode, sampleRate);

        g_python_initialized = true;

    } catch (const py::error_already_set& e) {
        fprintf(stderr, "Python init error: %s\n", e.what());
    }
}

// -------------------------------------------------------------
// Process audio buffer (mono or stereo)
// -------------------------------------------------------------
void process_audio(float* audioData,
                   int numSamples,
                   int numChannels)
{
    if (!g_python_initialized || !g_engine)
        return;

    try {
        py::array_t<float> audio_np;

        // Mono
        if (numChannels == 1) {
            audio_np = py::array_t<float>({numSamples}, audioData);
        }
        // Stereo (planar)
        else {
            audio_np = py::array_t<float>({numSamples, numChannels}, audioData);
        }

        // Call Python: engine.process_buffer(audio_np)
        py::array_t<float> result_np =
            g_engine.attr("process_buffer")(audio_np).cast<py::array_t<float>>();

        // Copy result back into audioData
        auto buf = result_np.request();
        float* result_ptr = static_cast<float*>(buf.ptr);

        std::size_t total = buf.size;
        for (std::size_t i = 0; i < total; ++i)
            audioData[i] = result_ptr[i];

    } catch (const py::error_already_set& e) {
        fprintf(stderr, "Python processing error: %s\n", e.what());
    }
}

// -------------------------------------------------------------
// Update Python mode dynamically
// -------------------------------------------------------------
void update_python_mode(const std::string& mode)
{
    if (!g_python_initialized || !g_engine)
        return;

    try {
        g_engine.attr("mode") = mode;
        g_engine.attr("engine").attr("mode") = mode;
    } catch (const py::error_already_set& e) {
        fprintf(stderr, "Python update mode error: %s\n", e.what());
    }
}

// -------------------------------------------------------------
// Shutdown Python interpreter
// -------------------------------------------------------------
void shutdown_python()
{
    if (!g_python_initialized)
        return;

    try {
        py::finalize_interpreter();
    } catch (...) {}

    g_python_initialized = false;
}
