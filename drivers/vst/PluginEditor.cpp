#include "PluginProcessor.h"
#include "PluginEditor.h"

// ==============================================================================
// Constructor
// ==============================================================================
IslaAudioProcessorEditor::IslaAudioProcessorEditor(IslaAudioProcessor& p)
    : AudioProcessorEditor(&p), processorRef(p)
{
    // Mode selector
    modeBox.addItem("Velvet", 1);
    modeBox.addItem("Legato", 2);
    modeBox.addItem("Melt",   3);

    modeBox.onChange = [this]()
    {
        const int id = modeBox.getSelectedId();
        std::string mode = "velvet";

        if (id == 2) mode = "legato";
        if (id == 3) mode = "melt";

        processorRef.setMode(mode);
        modeLabel.setText("Current Mode: " + juce::String(mode), juce::dontSendNotification);
    };

    modeBox.setSelectedId(1);
    addAndMakeVisible(modeBox);

    modeLabel.setText("Current Mode: velvet", juce::dontSendNotification);
    modeLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(modeLabel);

    setSize(300, 150);
}

// ==============================================================================
IslaAudioProcessorEditor::~IslaAudioProcessorEditor() {}

// ==============================================================================
void IslaAudioProcessorEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colours::black);

    g.setColour(juce::Colours::white);
    g.setFont(18.0f);
    g.drawText("ISLA", getLocalBounds(), juce::Justification::centredTop);
}

// ==============================================================================
void IslaAudioProcessorEditor::resized()
{
    modeBox.setBounds(50, 50, 200, 30);
    modeLabel.setBounds(50, 90, 200, 30);
}
