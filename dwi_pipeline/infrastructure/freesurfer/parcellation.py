from pathlib import Path
from typing import List, Optional, Tuple

from ...domain.models.bids_layout import BidsLayout
from ...domain.exceptions.errors import FreeSurferError

class FreeSurferValidator:
    """
    Performs strict validation of FreeSurfer output directories and required files.
    """
    def __init__(self, freesurfer_base_dir: Path):
        self.freesurfer_base_dir = freesurfer_base_dir

    def validate(self, subject: str, session: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Validates the presence of mandatory FreeSurfer output for a given subject and session.

        Args:
            subject (str): The subject ID (e.g., '01' for 'sub-01').
            session (str, optional): The session ID. Defaults to None.

        Returns:
            Tuple[bool, List[str]]: A tuple where the first element is True if
                                     validation passes, False otherwise. The second
                                     element is a list of error messages.
        """
        errors: List[str] = []
        sub_prefix = f"sub-{subject}"

        # Construct the expected FreeSurfer subject directory
        fs_subject_dir = self.freesurfer_base_dir / sub_prefix
        if not fs_subject_dir.is_dir():
            errors.append(f"FreeSurfer subject directory not found: {fs_subject_dir}")
            errors.append(f"Expected: {self.freesurfer_base_dir} / {sub_prefix}")
            errors.append("Please ensure recon-all has completed for this subject and the FreeSurfer output is correctly mounted.")
            return False, errors # No point checking for files if dir doesn't exist

        # Check for mandatory files within the mri subdirectory
        mri_dir = fs_subject_dir / "mri"
        if not mri_dir.is_dir():
            errors.append(f"FreeSurfer mri directory not found within subject dir: {mri_dir}")
            return False, errors
            
        required_files = [
            mri_dir / "aparc+aseg.mgz",  # Desikan-Killiany parcellation
            mri_dir / "brain.mgz",       # Brain extracted T1
            # mri_dir / "aparc.a2009s+aseg.mgz", # Destrieux - recommended but not strictly mandatory for core functionality
        ]

        for f in required_files:
            if not f.exists():
                errors.append(f"Missing mandatory FreeSurfer file: {f.name} in {f.parent}")
                errors.append(f"This indicates an incomplete or failed recon-all run for {sub_prefix}.")

        if not errors:
            return True, []
        else:
            return False, errors

    def get_parcellation_path(self, subject: str, parcellation_name: str) -> Path:
        """
        Returns the path to a specific FreeSurfer parcellation file.
        
        Args:
            subject (str): The subject ID.
            parcellation_name (str): The name of the parcellation (e.g., 'aparc+aseg', 'aparc.a2009s+aseg').
            
        Returns:
            Path: The full path to the parcellation file.
            
        Raises:
            FreeSurferError: If the requested parcellation file does not exist.
        """
        fs_subject_dir = self.freesurfer_base_dir / f"sub-{subject}"
        parcellation_file = fs_subject_dir / "mri" / f"{parcellation_name}.mgz"
        
        if not parcellation_file.exists():
            raise FreeSurferError(f"FreeSurfer parcellation '{parcellation_name}.mgz' not found for subject {subject} at {parcellation_file}")
            
        return parcellation_file
