from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..enums.species import Species

@dataclass
class ProcessingConfig:
    """
    Configuration parameters for a DWI processing pipeline run.
    
    This dataclass consolidates all user-defined and internally derived
    parameters necessary to execute the pipeline for a given subject/session.
    """
    subject: str = field(metadata={"help": "Subject ID (e.g., 'sub-01')."})
    
    # Required directories (non-default)
    output_dir: Path = field(metadata={"help": "Base directory for pipeline outputs."})
    work_dir: Path = field(metadata={"help": "Working directory for Nipype intermediate files."})
    bids_dir: Path = field(metadata={"help": "Root BIDS directory (read-only mount)."})
    freesurfer_dir: Path = field(metadata={"help": "FreeSurfer derivatives directory (read-only mount)."})

    # Optional fields must come after all required fields
    session: Optional[str] = field(default=None, metadata={"help": "Session ID (e.g., 'ses-01'), if applicable."})
    
    n_threads: int = field(default=4, metadata={"help": "Number of threads for parallel processing."})
    species: Species = field(default=Species.HUMAN, metadata={"help": "Species of the subject (e.g., HUMAN, NHP)."})
    rerun: bool = field(default=False, metadata={"help": "If True, force re-execution of all steps, ignoring Nipype cache."})
        
    # Derived unique identifier for this specific run's output
    run_id: str = field(init=False)

    def __post_init__(self):
        """Generates a unique run ID based on subject and session."""
        if self.session:
            self.run_id = f"{self.subject}_{self.session}"
        else:
            self.run_id = self.subject

    @property
    def nipype_work_dir(self) -> Path:
        """Returns the full path to the Nipype working directory for this run."""
        return self.work_dir / f"nipype_work_{self.run_id}"

    @property
    def subject_output_dir(self) -> Path:
        """
        Returns the BIDS-compliant output directory for the current subject/session
        within the base output_dir.
        """
        path = self.output_dir / f"sub-{self.subject}"
        if self.session:
            path /= f"ses-{self.session}"
        return path
