from pathlib import Path
from typing import Optional, List
import logging

from ...domain.models.bids_layout import BidsLayout
from ...domain.enums.distortion import DistortionStrategy
from ...domain.exceptions.errors import BidsValidationError

logger = logging.getLogger(__name__)


def _swap_nifti_ext(nifti_path: Path, new_ext: str) -> Path:
    """Replace .nii.gz (or .nii) with a new extension like .bval, .bvec, .json."""
    name = nifti_path.name
    if name.endswith('.nii.gz'):
        return nifti_path.parent / (name[:-7] + new_ext)
    elif name.endswith('.nii'):
        return nifti_path.parent / (name[:-4] + new_ext)
    return nifti_path.with_suffix(new_ext)


class BidsReader:
    """
    Discovers BIDS-compliant files for a given subject and session
    and constructs a BidsLayout object.
    """
    def __init__(self, bids_root: Path, freesurfer_dir: Path):
        if not bids_root.is_dir():
            raise FileNotFoundError(f"BIDS root directory not found: {bids_root}")
        self.bids_root = bids_root
        self.freesurfer_dir = freesurfer_dir

    def discover(self, subject: str, session: Optional[str] = None) -> BidsLayout:
        """
        Discovers relevant BIDS files for a subject and session.

        Args:
            subject (str): The subject ID (e.g., '01' for 'sub-01').
            session (str, optional): The session ID (e.g., '01' for 'ses-01'). Defaults to None.

        Returns:
            BidsLayout: An object containing paths to all discovered files.

        Raises:
            BidsValidationError: If critical BIDS files are not found.
        """
        sub_prefix = f"sub-{subject}"
        ses_prefix = f"_ses-{session}" if session else ""
        
        subject_dir = self.bids_root / sub_prefix
        if not subject_dir.is_dir():
            raise BidsValidationError(f"Subject directory not found: {subject_dir}", [f"Missing subject directory: {sub_prefix}"])

        base_search_path = subject_dir
        if session:
            session_dir = subject_dir / f"ses-{session}"
            if not session_dir.is_dir():
                raise BidsValidationError(f"Session directory not found: {session_dir}", [f"Missing session directory: {sub_prefix}{ses_prefix}"])
            base_search_path = session_dir

        # --- Discover DWI files ---
        dwi_nifti_pattern = f"{sub_prefix}{ses_prefix}*_dwi.nii.gz"
        dwi_nifti_files = list(base_search_path.glob(f"dwi/{dwi_nifti_pattern}"))
        if not dwi_nifti_files:
            dwi_nifti_files = list(base_search_path.glob(f"*/dwi/{dwi_nifti_pattern}"))
        if not dwi_nifti_files:
            raise BidsValidationError(f"No DWI NIfTI file found for {sub_prefix}{ses_prefix}", [f"Missing DWI file: {dwi_nifti_pattern}"])

        # Prefer dir-AP explicitly, then any non-PA file, then fall back to first match
        ap_files = [f for f in dwi_nifti_files if '_dir-AP_' in f.name]
        non_pa_files = [f for f in dwi_nifti_files if '_dir-PA_' not in f.name]
        if ap_files:
            dwi_ap = ap_files[0]
        elif non_pa_files:
            dwi_ap = non_pa_files[0]
        else:
            dwi_ap = dwi_nifti_files[0]

        dwi_ap_bval = _swap_nifti_ext(dwi_ap, '.bval')
        dwi_ap_bvec = _swap_nifti_ext(dwi_ap, '.bvec')
        dwi_ap_json = _swap_nifti_ext(dwi_ap, '.json')

        missing_dwi_files: List[str] = []
        for f in [dwi_ap_bval, dwi_ap_bvec, dwi_ap_json]:
            if not f.exists():
                missing_dwi_files.append(f"Missing required DWI file: {f.name}")
        if missing_dwi_files:
            raise BidsValidationError(f"Missing associated DWI files for {dwi_ap.name}", missing_dwi_files)

        # --- Discover T1w anatomical files ---
        t1w_nifti_pattern = f"{sub_prefix}{ses_prefix}*_T1w.nii.gz"
        t1w_nifti_files = list(base_search_path.glob(f"anat/{t1w_nifti_pattern}"))
        if not t1w_nifti_files:
            t1w_nifti_files = list(base_search_path.glob(f"*/anat/{t1w_nifti_pattern}"))
        if not t1w_nifti_files:
            raise BidsValidationError(f"No T1w NIfTI file found for {sub_prefix}{ses_prefix}", [f"Missing T1w file: {t1w_nifti_pattern}"])
        
        t1w = t1w_nifti_files[0]
        t1w_json = _swap_nifti_ext(t1w, '.json')
        if not t1w_json.exists():
            raise BidsValidationError(f"Missing JSON sidecar for T1w file: {t1w.name}", [f"Missing T1w JSON: {t1w_json.name}"])

        # --- Discover Optional Reverse Phase Encoding (RPE) DWI files ---
        dwi_pa: Optional[Path] = None
        dwi_pa_bval: Optional[Path] = None
        dwi_pa_bvec: Optional[Path] = None
        dwi_pa_json: Optional[Path] = None

        # Assuming RPE files will have a different 'dir' entity, e.g., 'dir-PA'
        rpe_pattern = f"{sub_prefix}{ses_prefix}*_dir-PA_dwi.nii.gz" # Common pattern for PA
        rpe_files = list(base_search_path.glob(f"dwi/{rpe_pattern}"))
        if rpe_files:
            dwi_pa = rpe_files[0]
            dwi_pa_bval = _swap_nifti_ext(dwi_pa, '.bval')
            dwi_pa_bvec = _swap_nifti_ext(dwi_pa, '.bvec')
            dwi_pa_json = _swap_nifti_ext(dwi_pa, '.json')
            if not all(f.exists() for f in [dwi_pa_bval, dwi_pa_bvec, dwi_pa_json]):
                logger.warning(f"Found PA DWI ({dwi_pa.name}) but missing associated .bval/.bvec/.json files. Will proceed without RPE correction.")
                dwi_pa = None # Invalidate if incomplete
                dwi_pa_bval = None
                dwi_pa_bvec = None
                dwi_pa_json = None
        
        # --- Discover Optional Fieldmap files ---
        phasediff_nifti: Optional[Path] = None
        phasediff_json: Optional[Path] = None
        magnitude1_nifti: Optional[Path] = None
        magnitude2_nifti: Optional[Path] = None

        fmap_path = base_search_path / "fmap"
        if fmap_path.is_dir():
            phasediff_pattern = f"{sub_prefix}{ses_prefix}*_phasediff.nii.gz"
            phasediff_files = list(fmap_path.glob(phasediff_pattern))
            if phasediff_files:
                phasediff_nifti = phasediff_files[0]
                phasediff_json = _swap_nifti_ext(phasediff_nifti, '.json')
                
                # Associated magnitude files
                magnitude1_files = list(fmap_path.glob(f"{sub_prefix}{ses_prefix}*_magnitude1.nii.gz"))
                magnitude2_files = list(fmap_path.glob(f"{sub_prefix}{ses_prefix}*_magnitude2.nii.gz"))
                
                if phasediff_json.exists() and magnitude1_files and magnitude2_files:
                    magnitude1_nifti = magnitude1_files[0]
                    magnitude2_nifti = magnitude2_files[0]
                else:
                    logger.warning(f"Found phasediff ({phasediff_nifti.name}) but missing associated JSON/magnitude files. Will proceed without fieldmap correction.")
                    phasediff_nifti = None # Invalidate if incomplete
                    phasediff_json = None
                    magnitude1_nifti = None
                    magnitude2_nifti = None

        # --- FreeSurfer directory (mandatory for now) ---
        # Try common FreeSurfer subject dir naming conventions:
        #   sub-XX, sub-XX_ses-YY, or sub-XXses-YY
        freesurfer_subject_dir = self.freesurfer_dir / sub_prefix
        if not freesurfer_subject_dir.is_dir() and session:
            freesurfer_subject_dir = self.freesurfer_dir / f"{sub_prefix}_ses-{session}"
        if not freesurfer_subject_dir.is_dir() and session:
            freesurfer_subject_dir = self.freesurfer_dir / f"{sub_prefix}ses-{session}"

        if not freesurfer_subject_dir.is_dir():
            raise BidsValidationError(
                f"FreeSurfer subject directory not found at {self.freesurfer_dir / sub_prefix}",
                [f"Expected FreeSurfer output for {sub_prefix} at {self.freesurfer_dir}"]
            )

        # Discover FreeSurfer parcellation files
        fs_brain = freesurfer_subject_dir / "mri" / "brain.mgz"
        fs_aparc_aseg = freesurfer_subject_dir / "mri" / "aparc+aseg.mgz"
        fs_aparc_destrieux = freesurfer_subject_dir / "mri" / "aparc.a2009s+aseg.mgz"

        if not fs_brain.exists():
            raise BidsValidationError(
                f"FreeSurfer brain.mgz not found at {fs_brain}",
                [f"Missing brain.mgz for {sub_prefix}"]
            )
        if not fs_aparc_aseg.exists():
            raise BidsValidationError(
                f"FreeSurfer aparc+aseg.mgz not found at {fs_aparc_aseg}",
                [f"Missing aparc+aseg.mgz for {sub_prefix}"]
            )
        if not fs_aparc_destrieux.exists():
            logger.warning(f"FreeSurfer aparc.a2009s+aseg.mgz not found at {fs_aparc_destrieux}. Destrieux atlas will be skipped.")
            fs_aparc_destrieux = None

        # Construct BidsLayout
        layout = BidsLayout(
            subject=subject,
            dwi_ap=dwi_ap,
            dwi_ap_bval=dwi_ap_bval,
            dwi_ap_bvec=dwi_ap_bvec,
            dwi_ap_json=dwi_ap_json,
            t1w=t1w,
            t1w_json=t1w_json,
            freesurfer_dir=freesurfer_subject_dir,
            session=session,
            dwi_pa=dwi_pa,
            dwi_pa_bval=dwi_pa_bval,
            dwi_pa_bvec=dwi_pa_bvec,
            dwi_pa_json=dwi_pa_json,
            phasediff_nifti=phasediff_nifti,
            phasediff_json=phasediff_json,
            magnitude1_nifti=magnitude1_nifti,
            magnitude2_nifti=magnitude2_nifti,
            fs_brain=fs_brain,
            fs_aparc_aseg=fs_aparc_aseg,
            fs_aparc_destrieux=fs_aparc_destrieux
        )
        
        # Populate derived properties (ShellType, DistortionStrategy) - these will be set later by metadata extractor
        # For now, we set placeholders.
        layout.shell_config = None # Will be set by metadata extractor
        layout.distortion_correction = DistortionStrategy.NONE # Will be set by metadata extractor

        return layout
