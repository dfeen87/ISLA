"""
Pipeline adapters for ISLA (legacy integration class names preserved).
Provides:
    - PhasedNotesBeamDoFn: Apache Beam DoFn for batch audio element processing.
    - PhasedNotesAirflowOperator: Airflow Operator for pipeline task integration.
    - PhasedNotesLuigiTask: Luigi Task for dependency-based audio processing.

Designed to be safely imported even if apache_beam, airflow, or luigi are not fully installed.
"""

import os
from typing import Union, Dict, Any
import numpy as np

from drivers.api import PhasedNotes, PhasedNotesBuffer


# --- Apache Beam Adapter ---
try:
    import apache_beam as beam
    BeamDoFn = beam.DoFn
except ImportError:
    # Safe fallback if Apache Beam is not installed
    class BeamDoFn:
        """Fallback base class when apache_beam is not installed."""
        pass


class PhasedNotesBeamDoFn(BeamDoFn):
    """
    Apache Beam DoFn to apply ISLA smoothing on audio streams.

    Can accept dictionary elements representing audio data, or paths.
    """
    def __init__(self, mode: str = "velvet", sr: int = 44100):
        super().__init__()
        self.mode = mode
        self.sr = sr
        self.buffer_processor = None

    def setup(self):
        """Initialize the DSP processor inside worker context."""
        self.buffer_processor = PhasedNotesBuffer(mode=self.mode, sr=self.sr)

    def process(self, element: Union[np.ndarray, Dict[str, Any]]):
        """
        Process an element in the Beam pipeline.

        If element is a numpy array, process directly.
        If element is a dictionary, expect an 'audio' key.
        """
        if self.buffer_processor is None:
            self.setup()

        if isinstance(element, np.ndarray):
            yield self.buffer_processor.process_buffer(element)
        elif isinstance(element, dict) and "audio" in element:
            audio = element["audio"]
            processed = self.buffer_processor.process_buffer(audio)
            output_elem = element.copy()
            output_elem["audio"] = processed
            yield output_elem
        else:
            # Pass through unrecognized elements
            yield element


# --- Airflow Adapter ---
try:
    from airflow.models import BaseOperator
except ImportError:
    # Safe fallback if Airflow is not installed
    class BaseOperator:
        """Fallback base class when Airflow is not installed."""
        def __init__(self, task_id: str, **kwargs):
            self.task_id = task_id
            for k, v in kwargs.items():
                setattr(self, k, v)


class PhasedNotesAirflowOperator(BaseOperator):
    """
    Airflow Operator to smooth an audio file from an input path to an output path.
    """
    def __init__(self, task_id: str, input_path: str, output_path: str, mode: str = "velvet", **kwargs):
        super().__init__(task_id=task_id, **kwargs)
        self.input_path = input_path
        self.output_path = output_path
        self.mode = mode

    def execute(self, context: Any) -> str:
        """Execute the audio smoothing task."""
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        processor = PhasedNotes(mode=self.mode)
        processor.process(self.input_path, self.output_path)
        return self.output_path


# --- Luigi Adapter ---
try:
    import luigi
    LuigiTask = luigi.Task
except ImportError:
    # Safe fallback if Luigi is not installed
    class LuigiTask:
        """Fallback base class when Luigi is not installed."""
        pass


class PhasedNotesLuigiTask(LuigiTask):
    """
    Luigi Task representing a stage in a local DAG processing audio.

    Subclasses should override:
        - input(): returns a luigi.LocalTarget for the raw audio file.
        - output(): returns a luigi.LocalTarget for the processed audio file.
    """
    mode = "velvet"

    def run(self):
        """Run the ISLA DSP on the input target."""
        input_target = self.input()
        output_target = self.output()

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_target.path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        processor = PhasedNotes(mode=self.mode)
        processor.process(input_target.path, output_target.path)
