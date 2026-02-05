"""
BIDS file discovery module for the MRtrix3 DWI pipeline.

This module provides functions to discover and validate BIDS-formatted
neuroimaging data for diffusion-weighted imaging processing.
"""

import os
import json
import glob
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
import numpy as np


@dataclass
class BIDSLayout:
    """Container for discovered BIDS file paths and metadata."""

    # Required paths
    bids_dir: str
    subject: str
    session: Optional[str] = None

    # DWI files (dir-AP is primary, dir-PA is secondary/optional)
    dwi_ap: Optional[str] = None
    dwi_ap_bvec: Optional[str] = None
    dwi_ap_bval: Optional[str] = None
    dwi_ap_json: Optional[str] = None

    dwi_pa: Optional[str] = None
    dwi_pa_bvec: Optional[str] = None
    dwi_pa_bval: Optional[str] = None
    dwi_pa_json: Optional[str] = None

    # Anatomical
    t1w: Optional[str] = None
    t1w_json: Optional[str] = None

    # Fieldmap files
    fmap_magnitude1: Optional[str] = None
    fmap_magnitude2: Optional[str] = None
    fmap_phasediff: Optional[str] = None
    fmap_phasediff_json: Optional[str] = None

    # FreeSurfer derivatives
    freesurfer_dir: Optional[str] = None
    freesurfer_version: Optional[str] = None
    fs_aparc_aseg: Optional[str] = None
    fs_aparc_dk: Optional[str] = None
    fs_aparc_destrieux: Optional[str] = None
    fs_brain: Optional[str] = None

    # Derived parameters
    pe_direction: Optional[str] = None
    total_readout_time: Optional[float] = None
    shell_config: Optional[str] = None  # 'single_shell' or 'multi_shell'
    distortion_correction: Optional[str] = None  # 'rpe_pair', 'fieldmap', or 'none'

    # Output directory
    output_dir: Optional[str] = None

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate that required files exist.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Must have at least one DWI file
        if not self.dwi_ap:
            errors.append("No dir-AP DWI file found")
        elif not os.path.exists(self.dwi_ap):
            errors.append(f"DWI AP file not found: {self.dwi_ap}")

        # Check bvec/bval for primary DWI
        if self.dwi_ap:
            if not self.dwi_ap_bvec or not os.path.exists(self.dwi_ap_bvec):
                errors.append(f"DWI AP bvec file not found")
            if not self.dwi_ap_bval or not os.path.exists(self.dwi_ap_bval):
                errors.append(f"DWI AP bval file not found")

        # T1w is required
        if not self.t1w:
            errors.append("No T1w anatomical file found")
        elif not os.path.exists(self.t1w):
            errors.append(f"T1w file not found: {self.t1w}")

        # Validate consistency of distortion correction strategy
        if self.distortion_correction == 'rpe_pair' and not self.dwi_pa:
            errors.append("rpe_pair distortion correction requires dir-PA DWI file")

        if self.distortion_correction == 'fieldmap':
            if not self.fmap_phasediff:
                errors.append("fieldmap distortion correction requires phasediff image")
            if not self.fmap_magnitude1 and not self.fmap_magnitude2:
                errors.append("fieldmap distortion correction requires magnitude image")

        return len(errors) == 0, errors

    def get_subject_session_prefix(self) -> str:
        """Get the BIDS subject/session prefix (e.g., 'sub-01_ses-01')."""
        if self.session:
            return f"{self.subject}_{self.session}"
        return self.subject


def discover_dwi_files(bids_dir: str, subject: str, session: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Discover DWI files in a BIDS directory.

    Looks for dir-AP and dir-PA DWI acquisitions.

    Args:
        bids_dir: Path to BIDS root directory
        subject: Subject ID (e.g., 'sub-01')
        session: Optional session ID (e.g., 'ses-01')

    Returns:
        Dictionary with paths to DWI files and their sidecars
    """
    result = {
        'dwi_ap': None, 'dwi_ap_bvec': None, 'dwi_ap_bval': None, 'dwi_ap_json': None,
        'dwi_pa': None, 'dwi_pa_bvec': None, 'dwi_pa_bval': None, 'dwi_pa_json': None,
    }

    # Build path to dwi directory
    if session:
        dwi_dir = os.path.join(bids_dir, subject, session, 'dwi')
    else:
        dwi_dir = os.path.join(bids_dir, subject, 'dwi')

    if not os.path.exists(dwi_dir):
        print(f"WARNING: DWI directory not found: {dwi_dir}")
        return result

    # Look for dir-AP DWI
    ap_patterns = [
        '*_dir-AP_dwi.nii.gz', '*_dir-AP_dwi.nii',
        '*_acq-AP_dwi.nii.gz', '*_acq-AP_dwi.nii',
        '*_dir-ap_dwi.nii.gz', '*_dir-ap_dwi.nii'
    ]

    for pattern in ap_patterns:
        matches = glob.glob(os.path.join(dwi_dir, pattern))
        if matches:
            result['dwi_ap'] = matches[0]
            base = result['dwi_ap'].replace('.nii.gz', '').replace('.nii', '')
            result['dwi_ap_bvec'] = base + '.bvec'
            result['dwi_ap_bval'] = base + '.bval'
            result['dwi_ap_json'] = base + '.json'
            break

    # Look for dir-PA DWI
    pa_patterns = [
        '*_dir-PA_dwi.nii.gz', '*_dir-PA_dwi.nii',
        '*_acq-PA_dwi.nii.gz', '*_acq-PA_dwi.nii',
        '*_dir-pa_dwi.nii.gz', '*_dir-pa_dwi.nii'
    ]

    for pattern in pa_patterns:
        matches = glob.glob(os.path.join(dwi_dir, pattern))
        if matches:
            result['dwi_pa'] = matches[0]
            base = result['dwi_pa'].replace('.nii.gz', '').replace('.nii', '')
            result['dwi_pa_bvec'] = base + '.bvec'
            result['dwi_pa_bval'] = base + '.bval'
            result['dwi_pa_json'] = base + '.json'
            break

    # Fallback: if no dir-AP/PA found, look for any DWI file
    if not result['dwi_ap']:
        patterns = ['*_dwi.nii.gz', '*_dwi.nii']
        for pattern in patterns:
            matches = glob.glob(os.path.join(dwi_dir, pattern))
            if matches:
                # Take the largest file as primary
                matches.sort(key=lambda x: os.path.getsize(x), reverse=True)
                result['dwi_ap'] = matches[0]
                base = result['dwi_ap'].replace('.nii.gz', '').replace('.nii', '')
                result['dwi_ap_bvec'] = base + '.bvec'
                result['dwi_ap_bval'] = base + '.bval'
                result['dwi_ap_json'] = base + '.json'
                print(f"INFO: No dir-AP/PA labels found, using {os.path.basename(result['dwi_ap'])} as primary")
                break

    return result


def discover_anat_files(bids_dir: str, subject: str, session: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Discover anatomical files in a BIDS directory.

    Args:
        bids_dir: Path to BIDS root directory
        subject: Subject ID (e.g., 'sub-01')
        session: Optional session ID (e.g., 'ses-01')

    Returns:
        Dictionary with paths to anatomical files
    """
    result = {'t1w': None, 't1w_json': None}

    # Build path to anat directory
    if session:
        anat_dir = os.path.join(bids_dir, subject, session, 'anat')
    else:
        anat_dir = os.path.join(bids_dir, subject, 'anat')

    if not os.path.exists(anat_dir):
        print(f"WARNING: Anat directory not found: {anat_dir}")
        return result

    # Look for T1w
    patterns = ['*_T1w.nii.gz', '*_T1w.nii']

    for pattern in patterns:
        matches = glob.glob(os.path.join(anat_dir, pattern))
        if matches:
            # Prefer run-1 or no run label
            matches.sort()
            result['t1w'] = matches[0]
            result['t1w_json'] = result['t1w'].replace('.nii.gz', '.json').replace('.nii', '.json')
            break

    return result


def discover_fieldmap_files(bids_dir: str, subject: str, session: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Discover fieldmap files in a BIDS directory.

    Supports phasediff/magnitude style fieldmaps.

    Args:
        bids_dir: Path to BIDS root directory
        subject: Subject ID (e.g., 'sub-01')
        session: Optional session ID (e.g., 'ses-01')

    Returns:
        Dictionary with paths to fieldmap files
    """
    result = {
        'magnitude1': None, 'magnitude2': None,
        'phasediff': None, 'phasediff_json': None
    }

    # Build path to fmap directory
    if session:
        fmap_dir = os.path.join(bids_dir, subject, session, 'fmap')
    else:
        fmap_dir = os.path.join(bids_dir, subject, 'fmap')

    if not os.path.exists(fmap_dir):
        return result

    # Look for magnitude images
    mag1_patterns = ['*_magnitude1.nii.gz', '*_magnitude1.nii']
    mag2_patterns = ['*_magnitude2.nii.gz', '*_magnitude2.nii']
    phasediff_patterns = ['*_phasediff.nii.gz', '*_phasediff.nii']

    for pattern in mag1_patterns:
        matches = glob.glob(os.path.join(fmap_dir, pattern))
        if matches:
            result['magnitude1'] = matches[0]
            break

    for pattern in mag2_patterns:
        matches = glob.glob(os.path.join(fmap_dir, pattern))
        if matches:
            result['magnitude2'] = matches[0]
            break

    for pattern in phasediff_patterns:
        matches = glob.glob(os.path.join(fmap_dir, pattern))
        if matches:
            result['phasediff'] = matches[0]
            result['phasediff_json'] = result['phasediff'].replace('.nii.gz', '.json').replace('.nii', '.json')
            break

    return result


def discover_freesurfer(bids_dir: str, subject: str) -> Dict[str, Optional[str]]:
    """
    Search for FreeSurfer derivatives in BIDS derivatives directory.

    Looks in derivatives/freesurfer*/sub-XX/ for FreeSurfer outputs.

    Args:
        bids_dir: Path to BIDS root directory
        subject: Subject ID (e.g., 'sub-01')

    Returns:
        Dictionary with FreeSurfer directory and file paths
    """
    result = {
        'freesurfer_dir': None,
        'freesurfer_version': None,
        'aparc_aseg': None,
        'aparc_dk': None,
        'aparc_destrieux': None,
        'brain': None
    }

    derivatives_dir = os.path.join(bids_dir, 'derivatives')
    if not os.path.exists(derivatives_dir):
        return result

    # Look for freesurfer derivatives directories (various naming conventions)
    fs_patterns = [
        'freesurfer*', 'FreeSurfer*', 'fmriprep*/sourcedata/freesurfer'
    ]

    fs_dirs = []
    for pattern in fs_patterns:
        matches = glob.glob(os.path.join(derivatives_dir, pattern))
        fs_dirs.extend(matches)

    if not fs_dirs:
        return result

    # Check each potential FreeSurfer directory for subject folder
    for fs_deriv in fs_dirs:
        subject_fs_dir = os.path.join(fs_deriv, subject)

        if not os.path.exists(subject_fs_dir):
            continue

        # Check for key FreeSurfer files
        mri_dir = os.path.join(subject_fs_dir, 'mri')
        if not os.path.exists(mri_dir):
            continue

        aparc_aseg = os.path.join(mri_dir, 'aparc+aseg.mgz')
        if os.path.exists(aparc_aseg):
            result['freesurfer_dir'] = subject_fs_dir
            result['aparc_aseg'] = aparc_aseg

            # Try to determine version from directory name
            fs_dirname = os.path.basename(fs_deriv)
            if '7' in fs_dirname:
                result['freesurfer_version'] = 'FreeSurfer7'
            elif '8' in fs_dirname:
                result['freesurfer_version'] = 'freesurfer8.0'
            else:
                result['freesurfer_version'] = 'FreeSurfer'

            # Check for additional parcellation files
            aparc_dk = os.path.join(mri_dir, 'aparc.DKTatlas+aseg.mgz')
            if os.path.exists(aparc_dk):
                result['aparc_dk'] = aparc_dk

            aparc_destrieux = os.path.join(mri_dir, 'aparc.a2009s+aseg.mgz')
            if os.path.exists(aparc_destrieux):
                result['aparc_destrieux'] = aparc_destrieux

            brain = os.path.join(mri_dir, 'brain.mgz')
            if os.path.exists(brain):
                result['brain'] = brain

            print(f"Found FreeSurfer derivatives at: {subject_fs_dir}")
            break

    return result


def detect_distortion_correction_strategy(dwi_files: Dict, fieldmap_files: Dict) -> str:
    """
    Detect the appropriate distortion correction strategy.

    Priority:
    1. rpe_pair: Both dir-AP and dir-PA DWI exist
    2. fieldmap: Single DWI + fieldmap files exist
    3. none: No reverse PE, no fieldmaps

    Args:
        dwi_files: Dictionary from discover_dwi_files()
        fieldmap_files: Dictionary from discover_fieldmap_files()

    Returns:
        Strategy string: 'rpe_pair', 'fieldmap', or 'none'
    """
    has_ap = dwi_files.get('dwi_ap') is not None
    has_pa = dwi_files.get('dwi_pa') is not None
    has_fieldmap = (
        fieldmap_files.get('phasediff') is not None and
        (fieldmap_files.get('magnitude1') is not None or fieldmap_files.get('magnitude2') is not None)
    )

    if has_ap and has_pa:
        return 'rpe_pair'
    elif has_fieldmap:
        return 'fieldmap'
    else:
        return 'none'


def detect_shell_configuration(bval_path: str) -> Tuple[str, List[float]]:
    """
    Detect shell configuration from bval file.

    Args:
        bval_path: Path to bval file

    Returns:
        Tuple of (shell_type, unique_bvals)
        shell_type: 'single_shell' or 'multi_shell'
    """
    if not os.path.exists(bval_path):
        raise FileNotFoundError(f"bval file not found: {bval_path}")

    bvals = np.loadtxt(bval_path)

    # Round to nearest 50 for grouping
    bvals_rounded = np.round(bvals / 50) * 50

    # Get unique non-zero b-values (ignore b=0)
    unique_bvals = np.unique(bvals_rounded[bvals_rounded > 50])

    shell_count = len(unique_bvals)

    print(f"Detected b-values: {unique_bvals.tolist()}")
    print(f"Shell count: {shell_count}")

    if shell_count >= 2:
        shell_type = 'multi_shell'
    else:
        shell_type = 'single_shell'

    return shell_type, unique_bvals.tolist()


def extract_dwi_parameters(json_path: str) -> Dict[str, Any]:
    """
    Extract DWI parameters from JSON sidecar.

    Args:
        json_path: Path to JSON sidecar file

    Returns:
        Dictionary with extracted parameters
    """
    result = {
        'total_readout_time': None,
        'pe_direction': None,
        'repetition_time': None
    }

    if not os.path.exists(json_path):
        print(f"WARNING: JSON sidecar not found: {json_path}")
        return result

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Total readout time
        if 'TotalReadoutTime' in data:
            result['total_readout_time'] = data['TotalReadoutTime']
        elif 'EffectiveEchoSpacing' in data and 'ReconMatrixPE' in data:
            result['total_readout_time'] = data['EffectiveEchoSpacing'] * (data['ReconMatrixPE'] - 1)

        # Phase encoding direction
        if 'PhaseEncodingDirection' in data:
            result['pe_direction'] = data['PhaseEncodingDirection']
        elif 'InPlanePhaseEncodingDirection' in data:
            # Convert from 'COL'/'ROW' to 'j'/'i'
            in_plane = data['InPlanePhaseEncodingDirection']
            if in_plane == 'COL':
                result['pe_direction'] = 'j'
            elif in_plane == 'ROW':
                result['pe_direction'] = 'i'

        # Repetition time
        if 'RepetitionTime' in data:
            result['repetition_time'] = data['RepetitionTime']

    except Exception as e:
        print(f"WARNING: Error reading JSON sidecar: {e}")

    return result


def extract_fieldmap_parameters(fieldmap_files: Dict) -> Dict[str, Any]:
    """
    Extract parameters from fieldmap JSON sidecars.

    Calculates DELTA_TE from echo times.

    Args:
        fieldmap_files: Dictionary from discover_fieldmap_files()

    Returns:
        Dictionary with fieldmap parameters including DELTA_TE
    """
    result = {
        'delta_te': None,
        'echo_time_1': None,
        'echo_time_2': None
    }

    phasediff_json = fieldmap_files.get('phasediff_json')
    if not phasediff_json or not os.path.exists(phasediff_json):
        return result

    try:
        with open(phasediff_json, 'r') as f:
            data = json.load(f)

        # BIDS specifies EchoTime1 and EchoTime2 in phasediff JSON
        if 'EchoTime1' in data and 'EchoTime2' in data:
            result['echo_time_1'] = data['EchoTime1']
            result['echo_time_2'] = data['EchoTime2']
            result['delta_te'] = abs(data['EchoTime2'] - data['EchoTime1'])
            print(f"Calculated DELTA_TE: {result['delta_te']:.6f}s")

    except Exception as e:
        print(f"WARNING: Error reading fieldmap JSON: {e}")

    return result


def create_bids_layout(
    bids_dir: str,
    subject: str,
    session: Optional[str] = None,
    output_dir: Optional[str] = None
) -> BIDSLayout:
    """
    Create a complete BIDSLayout by discovering all files.

    Args:
        bids_dir: Path to BIDS root directory
        subject: Subject ID (e.g., 'sub-01')
        session: Optional session ID (e.g., 'ses-01')
        output_dir: Optional output directory path

    Returns:
        Populated BIDSLayout object
    """
    layout = BIDSLayout(bids_dir=bids_dir, subject=subject, session=session)

    # Discover DWI files
    dwi_files = discover_dwi_files(bids_dir, subject, session)
    layout.dwi_ap = dwi_files.get('dwi_ap')
    layout.dwi_ap_bvec = dwi_files.get('dwi_ap_bvec')
    layout.dwi_ap_bval = dwi_files.get('dwi_ap_bval')
    layout.dwi_ap_json = dwi_files.get('dwi_ap_json')
    layout.dwi_pa = dwi_files.get('dwi_pa')
    layout.dwi_pa_bvec = dwi_files.get('dwi_pa_bvec')
    layout.dwi_pa_bval = dwi_files.get('dwi_pa_bval')
    layout.dwi_pa_json = dwi_files.get('dwi_pa_json')

    # Discover anatomical files
    anat_files = discover_anat_files(bids_dir, subject, session)
    layout.t1w = anat_files.get('t1w')
    layout.t1w_json = anat_files.get('t1w_json')

    # Discover fieldmap files
    fmap_files = discover_fieldmap_files(bids_dir, subject, session)
    layout.fmap_magnitude1 = fmap_files.get('magnitude1')
    layout.fmap_magnitude2 = fmap_files.get('magnitude2')
    layout.fmap_phasediff = fmap_files.get('phasediff')
    layout.fmap_phasediff_json = fmap_files.get('phasediff_json')

    # Discover FreeSurfer derivatives
    fs_files = discover_freesurfer(bids_dir, subject)
    layout.freesurfer_dir = fs_files.get('freesurfer_dir')
    layout.freesurfer_version = fs_files.get('freesurfer_version')
    layout.fs_aparc_aseg = fs_files.get('aparc_aseg')
    layout.fs_aparc_dk = fs_files.get('aparc_dk')
    layout.fs_aparc_destrieux = fs_files.get('aparc_destrieux')
    layout.fs_brain = fs_files.get('brain')

    # Detect distortion correction strategy
    layout.distortion_correction = detect_distortion_correction_strategy(dwi_files, fmap_files)

    # Extract DWI parameters
    if layout.dwi_ap_json and os.path.exists(layout.dwi_ap_json):
        params = extract_dwi_parameters(layout.dwi_ap_json)
        layout.pe_direction = params.get('pe_direction')
        layout.total_readout_time = params.get('total_readout_time')

    # Detect shell configuration
    if layout.dwi_ap_bval and os.path.exists(layout.dwi_ap_bval):
        try:
            shell_type, _ = detect_shell_configuration(layout.dwi_ap_bval)
            layout.shell_config = shell_type
        except Exception as e:
            print(f"WARNING: Could not detect shell configuration: {e}")

    # Set output directory
    if output_dir:
        layout.output_dir = output_dir
    else:
        # Default BIDS derivatives location
        if session:
            layout.output_dir = os.path.join(
                bids_dir, 'derivatives', 'mrtrix3', subject, session, 'dwi'
            )
        else:
            layout.output_dir = os.path.join(
                bids_dir, 'derivatives', 'mrtrix3', subject, 'dwi'
            )

    return layout


def print_layout_summary(layout: BIDSLayout) -> None:
    """Print a summary of the discovered BIDS layout."""
    print("\n=== BIDS Layout Summary ===")
    print(f"Subject: {layout.subject}")
    if layout.session:
        print(f"Session: {layout.session}")

    print(f"\nDWI Files:")
    print(f"  dir-AP: {os.path.basename(layout.dwi_ap) if layout.dwi_ap else 'Not found'}")
    print(f"  dir-PA: {os.path.basename(layout.dwi_pa) if layout.dwi_pa else 'Not found'}")

    print(f"\nAnatomical:")
    print(f"  T1w: {os.path.basename(layout.t1w) if layout.t1w else 'Not found'}")

    print(f"\nFieldmaps:")
    print(f"  magnitude1: {os.path.basename(layout.fmap_magnitude1) if layout.fmap_magnitude1 else 'Not found'}")
    print(f"  magnitude2: {os.path.basename(layout.fmap_magnitude2) if layout.fmap_magnitude2 else 'Not found'}")
    print(f"  phasediff: {os.path.basename(layout.fmap_phasediff) if layout.fmap_phasediff else 'Not found'}")

    print(f"\nFreeSurfer:")
    if layout.freesurfer_dir:
        print(f"  Version: {layout.freesurfer_version}")
        print(f"  Directory: {layout.freesurfer_dir}")
    else:
        print(f"  Not found in derivatives")

    print(f"\nProcessing Configuration:")
    print(f"  Shell config: {layout.shell_config or 'Unknown'}")
    print(f"  Distortion correction: {layout.distortion_correction}")
    print(f"  PE direction: {layout.pe_direction or 'Unknown'}")
    print(f"  Total readout time: {layout.total_readout_time or 'Unknown'}")

    print(f"\nOutput directory: {layout.output_dir}")
