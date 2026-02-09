"""Constants for the DWI pipeline, including MRtrix3 LUT discovery."""

import os
import shutil
from pathlib import Path

# LUT filenames shipped with MRtrix3
FS_COLOR_LUT = "FreeSurferColorLUT.txt"
FS_DEFAULT_LUT = "fs_default.txt"       # DK atlas (84 regions)
FS_A2009S_LUT = "fs_a2009s.txt"          # Destrieux atlas (164 regions)

_COMMON_LUT_DIRS = [
    "/usr/share/mrtrix3/labelconvert",
    "/usr/local/share/mrtrix3/labelconvert",
    "/opt/mrtrix3/share/mrtrix3/labelconvert",
]

_COMMON_FS_DIRS = [
    "/usr/local/freesurfer",
    "/opt/freesurfer",
]


def find_mrtrix_lut_dir() -> Path:
    """
    Locate the MRtrix3 labelconvert LUT directory.

    Search order:
    1. MRTRIX_LUTS environment variable
    2. Common container installation paths
    3. Relative to the labelconvert binary (via shutil.which)

    Returns:
        Path to the directory containing MRtrix3 LUT files.

    Raises:
        FileNotFoundError: If the LUT directory cannot be found.
    """
    # 1. Check environment variable
    env_path = os.environ.get("MRTRIX_LUTS")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    # 2. Check common container paths
    for candidate in _COMMON_LUT_DIRS:
        p = Path(candidate)
        if p.is_dir():
            return p

    # 3. Derive from labelconvert binary location
    labelconvert_bin = shutil.which("labelconvert")
    if labelconvert_bin:
        # e.g. /usr/local/bin/labelconvert -> /usr/local/share/mrtrix3/labelconvert/
        bin_dir = Path(labelconvert_bin).resolve().parent
        share_dir = bin_dir.parent / "share" / "mrtrix3" / "labelconvert"
        if share_dir.is_dir():
            return share_dir

    raise FileNotFoundError(
        "Could not find MRtrix3 LUT directory. Set the MRTRIX_LUTS environment variable "
        "or ensure MRtrix3 is installed in a standard location."
    )


def find_freesurfer_color_lut(freesurfer_dir: Path | None = None) -> Path:
    """
    Locate FreeSurferColorLUT.txt, which ships with FreeSurfer (not MRtrix3).

    Search order:
    1. Provided freesurfer_dir (the top-level FS derivatives mount)
    2. FREESURFER_HOME environment variable
    3. Common container installation paths

    Args:
        freesurfer_dir: Top-level FreeSurfer derivatives directory (e.g. /freesurfer).

    Returns:
        Path to FreeSurferColorLUT.txt.

    Raises:
        FileNotFoundError: If FreeSurferColorLUT.txt cannot be found.
    """
    target = FS_COLOR_LUT

    # 1. Check the provided freesurfer derivatives dir
    if freesurfer_dir:
        p = Path(freesurfer_dir) / target
        if p.is_file():
            return p

    # 2. Check FREESURFER_HOME
    fs_home = os.environ.get("FREESURFER_HOME")
    if fs_home:
        p = Path(fs_home) / target
        if p.is_file():
            return p

    # 3. Check common container paths
    for candidate in _COMMON_FS_DIRS:
        p = Path(candidate) / target
        if p.is_file():
            return p

    raise FileNotFoundError(
        f"Could not find {target}. Ensure FreeSurfer is installed or set FREESURFER_HOME. "
        f"Searched: {freesurfer_dir}, $FREESURFER_HOME={fs_home}, {_COMMON_FS_DIRS}"
    )
