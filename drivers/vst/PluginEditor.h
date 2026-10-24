#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "PluginProcessor.h"

class IslaAudioProcessorEditor : public juce::AudioProcessorEditor
{
public:
    explicit IslaAudioProcessorEditor (IslaAudioProcessor&);
    ~IslaAudioProcessorEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    IslaAudioProcessor& processorRef;

    // ============================================================
    // GUI components
    juce::ComboBox modeBox;
    juce::Label modeLabel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (IslaAudioProcessorEditor)
};
