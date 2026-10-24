"""ISLA pipeline integration interfaces (legacy classes retained)."""
from phased_music_notes.pipeline_adapters import (PhasedNotesBeamDoFn, PhasedNotesAirflowOperator, PhasedNotesLuigiTask)

IslaBeamDoFn = PhasedNotesBeamDoFn
IslaAirflowOperator = PhasedNotesAirflowOperator
IslaLuigiTask = PhasedNotesLuigiTask
