#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <string>

// Forward declaration of your Python bridge
void init_python(int sampleRate, const std::string& mode = "velvet");
void shutdown_python();
void process_audio(float* audioData, int numSamples, int numChannels);

class IslaAudioProcessor : public juce::AudioProcessor
{
public:
    IslaAudioProcessor();
    ~IslaAudioProcessor() override;

    //==============================================================================
    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;

    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;

    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    //==============================================================================
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override;

    //==============================================================================
    const juce::String getName() const override;

    bool acceptsMidi() const override;
    bool producesMidi() const override;
    double getTailLengthSeconds() const override;

    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

    //==============================================================================
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    //==============================================================================
    // Called by PluginEditor to switch DSP modes
    void setMode(const std::string& mode);

private:
    std::string currentMode = "velvet";

    // Profiling variables
    long long totalProcessingTimeMicroseconds = 0;
    long long totalBlocksProcessed = 0;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(IslaAudioProcessor)
};
