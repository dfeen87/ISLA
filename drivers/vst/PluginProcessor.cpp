#include "PluginProcessor.h"
#include "PluginEditor.h"
#include <chrono>

// Python bridge
extern void init_python(int sampleRate, const std::string& mode);
extern void process_audio(float* audioData, int numSamples, int numChannels);
extern void update_python_mode(const std::string& mode);
extern void shutdown_python();

// ==============================================================================
// Constructor
// ==============================================================================
IslaAudioProcessor::IslaAudioProcessor()
#ifndef JucePlugin_PreferredChannelConfigurations
     : AudioProcessor(BusesProperties()
         .withInput("Input",  juce::AudioChannelSet::stereo(), true)
         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
#endif
{
}

// ==============================================================================
IslaAudioProcessor::~IslaAudioProcessor()
{
    shutdown_python();
}

// ==============================================================================
const juce::String IslaAudioProcessor::getName() const
{
    return JucePlugin_Name;
}

bool IslaAudioProcessor::acceptsMidi() const
{
#if JucePlugin_WantsMidiInput
    return true;
#else
    return false;
#endif
}

bool IslaAudioProcessor::producesMidi() const
{
#if JucePlugin_ProducesMidiOutput
    return true;
#else
    return false;
#endif
}

double IslaAudioProcessor::getTailLengthSeconds() const
{
    return 0.0;
}

// ==============================================================================
void IslaAudioProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    juce::ignoreUnused(samplesPerBlock);

    // Initialize Python DSP engine
    init_python((int)sampleRate, "velvet");
}

// ==============================================================================
void IslaAudioProcessor::releaseResources()
{
#if JUCE_DEBUG
    if (totalBlocksProcessed > 0)
    {
        double avg = (double)totalProcessingTimeMicroseconds / totalBlocksProcessed;
        juce::Logger::writeToLog("ISLA Profiling: Average DSP time per block: " + juce::String(avg) + " microseconds.");
    }
#endif

    shutdown_python();
}

// ==============================================================================
bool IslaAudioProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    // Only stereo supported for now
    if (layouts.getMainOutputChannelSet() != juce::AudioChannelSet::stereo())
        return false;

    return true;
}

// ==============================================================================
void IslaAudioProcessor::processBlock(juce::AudioBuffer<float>& buffer,
                                             juce::MidiBuffer&)
{
    const int numSamples  = buffer.getNumSamples();
    const int numChannels = buffer.getNumChannels();

    float* left  = buffer.getWritePointer(0);
    float* right = (numChannels > 1 ? buffer.getWritePointer(1) : nullptr);

    // ---------------------------------------------------------
    // Build contiguous planar buffer for Python
    // ---------------------------------------------------------
    std::vector<float> temp;

    if (numChannels == 1)
    {
        temp.assign(left, left + numSamples);
    }
    else
    {
        temp.resize(numSamples * 2);
        for (int i = 0; i < numSamples; ++i)
        {
            temp[i * 2 + 0] = left[i];
            temp[i * 2 + 1] = right[i];
        }
    }

    // ---------------------------------------------------------
    // Call Python DSP
    // ---------------------------------------------------------
    auto start = std::chrono::high_resolution_clock::now();

    process_audio(temp.data(), numSamples, numChannels);

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();

    totalProcessingTimeMicroseconds += duration;
    totalBlocksProcessed++;

    // ---------------------------------------------------------
    // Copy back into JUCE buffer
    // ---------------------------------------------------------
    if (numChannels == 1)
    {
        memcpy(left, temp.data(), numSamples * sizeof(float));
    }
    else
    {
        for (int i = 0; i < numSamples; ++i)
        {
            left[i]  = temp[i * 2 + 0];
            right[i] = temp[i * 2 + 1];
        }
    }
}

// ==============================================================================
juce::AudioProcessorEditor* IslaAudioProcessor::createEditor()
{
    return new IslaAudioProcessorEditor(*this);
}

bool IslaAudioProcessor::hasEditor() const
{
    return true;
}

// ==============================================================================
void IslaAudioProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    juce::ignoreUnused(destData);
}

void IslaAudioProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    juce::ignoreUnused(data, sizeInBytes);
}

// ==============================================================================
void IslaAudioProcessor::setMode(const std::string& mode)
{
    currentMode = mode;
    update_python_mode(mode);
}

// ==============================================================================
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new IslaAudioProcessor();
}
