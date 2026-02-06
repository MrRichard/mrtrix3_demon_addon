from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..enums.shell_type import ShellType
from ..enums.distortion import DistortionStrategy

@dataclass
class BidsLayout:
    """
    Represents the discovered BIDS file structure for a subject and session.

    This dataclass holds paths to all relevant input files (DWI, T1w, Fieldmaps)
    and derived metadata required for processing. It also includes basic validation
    to ensure all necessary files are present.
    """
    subject: str
    
    # DWI files (required)
    dwi_ap: Path = field(metadata={"help": "Path to the Anterior-Posterior DWI NIfTI file."})
    dwi_ap_bval: Path = field(metadata={"help": "Path to the b-value file for dwi_ap."})
    dwi_ap_bvec: Path = field(metadata={"help": "Path to the b-vector file for dwi_ap."})
    dwi_ap_json: Path = field(metadata={"help": "Path to the JSON sidecar for dwi_ap."})

    # T1w anatomical image (required)
    t1w: Path = field(metadata={"help": "Path to the T1-weighted anatomical NIfTI file."})
    t1w_json: Path = field(metadata={"help": "Path to the JSON sidecar for T1w."})

    # FreeSurfer derivatives directory (mandatory)
    freesurfer_dir: Path = field(metadata={"help": "Path to the FreeSurfer subject directory (e.g., /freesurfer/sub-XX)."})

    # Optional fields must come after all required fields
    session: Optional[str] = field(default=None)

    # Reverse phase-encoding DWI files (optional for RPE_PAIR correction)
    dwi_pa: Optional[Path] = field(default=None, metadata={"help": "Path to the Posterior-Anterior DWI NIfTI file (optional)."})
    dwi_pa_bval: Optional[Path] = field(default=None, metadata={"help": "Path to the b-value file for dwi_pa (optional)."})
    dwi_pa_bvec: Optional[Path] = field(default=None, metadata={"help": "Path to the b-vector file for dwi_pa (optional)."})
    dwi_pa_json: Optional[Path] = field(default=None, metadata={"help": "Path to the JSON sidecar for dwi_pa (optional)."})

    # Fieldmap files (optional for FIELDMAP correction)
    phasediff_nifti: Optional[Path] = field(default=None, metadata={"help": "Path to the phasediff NIfTI file (optional)."})
    phasediff_json: Optional[Path] = field(default=None, metadata={"help": "Path to the JSON sidecar for phasediff (optional)."})
    magnitude1_nifti: Optional[Path] = field(default=None, metadata={"help": "Path to the magnitude1 NIfTI file (optional)."})
    magnitude2_nifti: Optional[Path] = field(default=None, metadata={"help": "Path to the magnitude2 NIfTI file (optional)."})


    # Derived properties (set during discovery/validation)
    shell_config: ShellType = field(init=False)
    distortion_correction: DistortionStrategy = field(init=False)
    
    def __post_init__(self):
        """Perform post-initialization validation and setup."""
        # This will be populated by BidsReader, but initialized here for type hinting
        pass

    def validate_paths(self) -> Tuple[bool, List[str]]:
        """
        Validates that all specified Path objects actually exist on the filesystem.

        Returns:
            A tuple containing:
            - bool: True if all paths exist, False otherwise.
            - list[str]: A list of error messages for non-existent paths.
        """
        errors: List[str] = []
        
        # Required DWI files
        for f in [self.dwi_ap, self.dwi_ap_bval, self.dwi_ap_bvec, self.dwi_ap_json]:
            if not f.exists():
                errors.append(f"Required DWI file not found: {f}")
        
        # Required T1w files
        for f in [self.t1w, self.t1w_json]:
            if not f.exists():
                errors.append(f"Required T1w file not found: {f}")
        
        # Mandatory FreeSurfer directory
        if not self.freesurfer_dir.is_dir():
            errors.append(f"FreeSurfer directory not found or is not a directory: {self.freesurfer_dir}")

        # Optional RPE_PAIR files
        if self.dwi_pa:
            for f in [self.dwi_pa, self.dwi_pa_bval, self.dwi_pa_bvec, self.dwi_pa_json]:
                if f and not f.exists(): # f might be None if it's an optional part of the pair
                    errors.append(f"Optional PA DWI file not found: {f} (present in BIDSLayout but missing)")

        # Optional FIELDMAP files
        if self.phasediff_nifti:
            for f in [self.phasediff_nifti, self.phasediff_json, self.magnitude1_nifti, self.magnitude2_nifti]:
                if f and not f.exists(): # f might be None if it's an optional part of the fieldmap set
                    errors.append(f"Optional fieldmap file not found: {f} (present in BIDSLayout but missing)")

        return not bool(errors), errors

    def get_subject_output_path(self, base_output_dir: Path) -> Path:
        """
        Generates the BIDS-compliant output path for the subject/session.

        Args:
            base_output_dir (Path): The base derivatives output directory.

        Returns:
            Path: The full output path for the current subject/session.
        """
        output_path = base_output_dir / f"sub-{self.subject}"
        if self.session:
            output_path /= f"ses-{self.session}"
        return output_path
