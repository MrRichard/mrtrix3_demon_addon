import argparse
from SlurmBatch import SLURMFileCreator
from ImageTypeChecker import ImageTypeChecker
import glob
import json
import os
import logging
import numpy as np

# ENHANCED 7/25/2025: Added comprehensive fieldmap support for distortion correction

# ADDED 7/25/2025: New function to find fieldmap files in the mrtrix3_inputs directory
def find_fieldmap_files(subject_folder):
    """
    Find fieldmap files in the mrtrix3_inputs directory.
    Returns dictionary with fieldmap file paths and metadata.
    """
    mrtrix3_inputs = os.path.join(subject_folder, "mrtrix3_inputs")
    
    if not os.path.exists(mrtrix3_inputs):
        return {}
    
    fieldmap_files = {}
    
    # Look for fieldmap files
    fieldmap_patterns = {
        'FIELDMAP_MAG1': 'FIELDMAP_MAG1.nii.gz',
        'FIELDMAP_MAG2': 'FIELDMAP_MAG2.nii.gz', 
        'FIELDMAP_PHASEDIFF': 'FIELDMAP_PHASEDIFF.nii.gz'
    }
    
    for key, filename in fieldmap_patterns.items():
        nii_file = os.path.join(mrtrix3_inputs, filename)
        json_file = os.path.join(mrtrix3_inputs, filename.replace('.nii.gz', '.json'))
        
        if os.path.exists(nii_file):
            fieldmap_files[key] = {
                'nifti_path': nii_file,
                'json_path': json_file if os.path.exists(json_file) else None
            }
            print(f"Found fieldmap file: {filename}")
        
    return fieldmap_files

# ADDED 7/25/2025: New function to extract DELTA_TE and other parameters from fieldmap JSON files
def extract_fieldmap_parameters(fieldmap_files):
    """
    Extract DELTA_TE and other parameters from fieldmap JSON files.
    """
    if not fieldmap_files:
        return {}
    
    # Get echo times from magnitude images
    echo_times = []
    
    for mag_key in ['FIELDMAP_MAG1', 'FIELDMAP_MAG2']:
        if mag_key in fieldmap_files and fieldmap_files[mag_key]['json_path']:
            try:
                with open(fieldmap_files[mag_key]['json_path'], 'r') as f:
                    json_data = json.load(f)
                    echo_time = json_data.get('EchoTime', 0)
                    echo_times.append(echo_time)
                    print(f"{mag_key} Echo Time: {echo_time:.6f}s")
            except Exception as e:
                print(f"WARNING: Could not read {mag_key} JSON: {e}")
    
    # Calculate DELTA_TE
    delta_te = 2.46  # Default Siemens value
    if len(echo_times) == 2:
        delta_te = abs(echo_times[1] - echo_times[0])
        print(f"Calculated DELTA_TE: {delta_te:.6f}s")
    else:
        print(f"WARNING: Could not calculate DELTA_TE, using default: {delta_te}s")
    
    # Try to get phase encoding direction from one of the magnitude images
    pe_dir = "j"  # Default
    readout_time = 0.1  # Default
    
    for mag_key in ['FIELDMAP_MAG1', 'FIELDMAP_MAG2']:
        if mag_key in fieldmap_files and fieldmap_files[mag_key]['json_path']:
            try:
                with open(fieldmap_files[mag_key]['json_path'], 'r') as f:
                    json_data = json.load(f)
                    
                    # Get phase encoding direction
                    if 'PhaseEncodingDirection' in json_data:
                        pe_dir = json_data['PhaseEncodingDirection']
                        break
                    elif 'InPlanePhaseEncodingDirection' in json_data:
                        pe_dir = json_data['InPlanePhaseEncodingDirection'] 
                        break
                        
            except Exception as e:
                print(f"WARNING: Could not read PE direction from {mag_key}: {e}")
    
    return {
        'DELTA_TE': delta_te,
        'FIELDMAP_PE_DIR': pe_dir,
        'echo_times': echo_times
    }

# ADDED 7/25/2025: New function to detect fieldmap configuration and validate completeness
def detect_fieldmap_configuration(subject_folder):
    """
    Detect if fieldmaps are available and what type.
    Returns configuration info and file paths.
    """
    fieldmap_files = find_fieldmap_files(subject_folder)
    
    if not fieldmap_files:
        return {
            'available': False,
            'type': None,
            'files': {},
            'parameters': {}
        }
    
    # Check what type of fieldmap we have
    has_mag1 = 'FIELDMAP_MAG1' in fieldmap_files
    has_mag2 = 'FIELDMAP_MAG2' in fieldmap_files
    has_phase = 'FIELDMAP_PHASEDIFF' in fieldmap_files
    
    if has_mag1 and has_mag2 and has_phase:
        fieldmap_type = 'dual_echo_gre'
        print("Detected: Dual-echo GRE fieldmap (ideal for distortion correction)")
    elif (has_mag1 or has_mag2) and has_phase:
        fieldmap_type = 'single_echo_gre'
        print("Detected: Single-echo GRE fieldmap")
    else:
        print("WARNING: Incomplete fieldmap data detected")
        return {
            'available': False,
            'type': 'incomplete',
            'files': fieldmap_files,
            'parameters': {}
        }
    
    # Extract parameters
    parameters = extract_fieldmap_parameters(fieldmap_files)
    
    return {
        'available': True,
        'type': fieldmap_type,
        'files': fieldmap_files,
        'parameters': parameters
    }

def find_t1_image(input_path):
    """Find T1 anatomical file."""
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-tfl3d116.nii*')
    matching_files = glob.glob(pattern)

    if len(matching_files) == 0:
        pattern = os.path.join(os.path.join(input_path,'nifti'), '*-tfl3d116ns.nii*')
        matching_files = glob.glob(pattern)
    
    return matching_files

def find_t1_brainmask_image(input_path):
    """Find T1 brain mask file."""
    if os.path.isdir(os.path.join(input_path,'nifti','cat12')):
        pattern = os.path.join(os.path.join(input_path,'nifti','cat12'), '*tfl3d116*_bet_mask.nii*')
    else:
        pattern = os.path.join(os.path.join(input_path,'nifti','vbm8'), '*tfl3d116*_bet_mask.nii*')
        
    matching_files = glob.glob(pattern)
    
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_dti_directory(subject_folder):
    """
    Find DTI directory which may have series number suffix (e.g., DTI_S0006).
    Returns the DTI directory path and the directory name.
    """
    print(f"DEBUG: Searching in {subject_folder}")
    
    # Try different DTI directory patterns
    patterns = [
        'DTI_S*', 'DTI*', 'DWI_S*', 'DWI*', 'DIFFUSION_S*', 'DIFFUSION*'
    ]
    
    dti_dirs = []
    for pattern in patterns:
        search_pattern = os.path.join(subject_folder, pattern)
        print(f"DEBUG: Searching pattern: {search_pattern}")
        dirs = glob.glob(search_pattern)
        dirs = [d for d in dirs if os.path.isdir(d)]
        print(f"DEBUG: Found for pattern {pattern}: {[os.path.basename(d) for d in dirs]}")
        dti_dirs.extend(dirs)
    
    if not dti_dirs:
        print("DEBUG: No pattern matches found, trying fallback search...")
        try:
            all_dirs = [d for d in os.listdir(subject_folder) 
                       if os.path.isdir(os.path.join(subject_folder, d))]
            print(f"DEBUG: All directories: {all_dirs}")
            for dirname in all_dirs:
                if any(keyword in dirname.upper() for keyword in ['DTI', 'DWI', 'DIFFUSION']):
                    dti_dirs.append(os.path.join(subject_folder, dirname))
                    print(f"DEBUG: Added fallback directory: {dirname}")
        except Exception as e:
            print(f"DEBUG: Error in fallback search: {e}")
    
    if not dti_dirs:
        print("ERROR: No DTI/DWI directory found")
        return None, None
    
    dti_dirs = list(set(dti_dirs))
    
    tmp_dir = os.path.join(subject_folder, 'tmp')
    if os.path.exists(tmp_dir):
        try:
            files = os.listdir(tmp_dir)
            dicom_files = [f for f in files if f.lower().endswith(('.dcm', '.ima', '.dicom')) or not '.' in f]
            if dicom_files:
                print(f"DEBUG: Found tmp/ at subject root with {len(dicom_files)} potential DICOM files")
            else:
                print(f"DEBUG: Found tmp/ at subject root but no DICOM files")
        except Exception as e:
            print(f"DEBUG: Error checking tmp/ directory: {e}")
    else:
        print(f"DEBUG: No tmp/ directory found at subject root: {tmp_dir}")
    
    if len(dti_dirs) > 1:
        print(f"Multiple DTI directories found: {[os.path.basename(d) for d in dti_dirs]}")
        dti_dirs.sort()
        selected_dir = dti_dirs[0]
        print(f"Selected: {os.path.basename(selected_dir)}")
    else:
        selected_dir = dti_dirs[0]
        print(f"Found DTI directory: {os.path.basename(selected_dir)}")
    
    return selected_dir, os.path.basename(selected_dir)

def find_dwi_brainmask_image(dti_folder):
    """Find pre-existing diffusion brain mask (*epb0_T2_mask.nii) in the DTI folder."""
    pattern = os.path.join(dti_folder, '*epb*_T2_bet_mask.nii')
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        pattern_gz = os.path.join(dti_folder, '*epb*_T2_bet_mask.nii.gz')
        matching_files = glob.glob(pattern_gz)
    
    if matching_files:
        print(f"Found pre-existing DWI brain mask: {matching_files[0]}")
        return matching_files
    else:
        print(f"WARNING: No pre-existing DWI brain mask found in {dti_folder}")
        print("Expected pattern: *epb0_T2_mask.nii or *epb0_T2_mask.nii.gz")
        return []

def find_t2_image(input_path):
    """Find T2 anatomical file."""
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-spc2*.info')
    matching_files = glob.glob(pattern)
    
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_flair_image(input_path):
    """Find FLAIR image file."""
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-spcir*.info')
    matching_files = glob.glob(pattern)
    
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_dti_mosaic(dti_folder, subject_folder):
    """Find DTI MOSAIC file in the nifti2 directory within the DTI folder."""
    nifti2_dir = os.path.join(subject_folder, "nifti2")
    
    if not os.path.exists(nifti2_dir):
        print(f"ERROR: nifti2 directory not found at {nifti2_dir}")
        print("Run DICOM conversion first using ImageTypeChecker")
        return None
    
    patterns = [
        "*DTI*.nii.gz", "*dti*.nii.gz"
    ]
    
    dti_files = []
    for pattern in patterns:
        files = glob.glob(os.path.join(nifti2_dir, pattern))
        files = [f for f in files if 'PHASE' not in f and 'SBREF' not in f and 'fieldmap' not in f.lower()]
        dti_files.extend(files)
        if files:
            print(f"DEBUG: Pattern {pattern} found: {[os.path.basename(f) for f in files]}")
    
    if not dti_files:
        all_files = glob.glob(os.path.join(nifti2_dir, "*.nii.gz"))
        dti_files = [f for f in all_files if 'PHASE' not in f and 'SBREF' not in f and 'fieldmap' not in f.lower()]
        
        if dti_files:
            print(f"WARNING: No explicit DTI files found. Using: {[os.path.basename(f) for f in dti_files]}")
        else:
            print("ERROR: No suitable DTI files found in nifti2 directory")
            print(f"Available files: {os.listdir(nifti2_dir) if os.path.exists(nifti2_dir) else 'none'}")
            return None
    
    if len(dti_files) > 1:
        file_sizes = {f: os.path.getsize(f) for f in dti_files}
        largest_file = max(file_sizes, key=file_sizes.get)
        print(f"Multiple DTI files found. Selected largest: {os.path.basename(largest_file)}")
        return largest_file
    else:
        print(f"Found DTI file: {os.path.basename(dti_files[0])}")
        return dti_files[0]

# ENHANCED 7/25/2025: Updated to copy fieldmap files along with DTI files
def create_mrtrix3_inputs_from_nifti2(dti_folder, subject_folder):
    """Create mrtrix3_inputs directory and copy/process files from nifti2."""
    nifti2_dir = os.path.join(subject_folder, "nifti2")
    mrtrix3_inputs = os.path.join(subject_folder, "mrtrix3_inputs")
    
    if not os.path.exists(nifti2_dir):
        raise FileNotFoundError(f"nifti2 directory not found: {nifti2_dir}")
    
    if not os.path.exists(mrtrix3_inputs):
        os.makedirs(mrtrix3_inputs)
        print(f"Created mrtrix3_inputs directory: {mrtrix3_inputs}")
    
    dti_file = find_dti_mosaic(dti_folder, subject_folder)
    if not dti_file:
        raise FileNotFoundError("No DTI file found in nifti2 directory")
    
    import shutil
    
    # Copy DTI files
    target_dti = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
    if not os.path.exists(target_dti):
        shutil.copy2(dti_file, target_dti)
        print(f"Copied DTI file: {os.path.basename(dti_file)} -> DTI_MOSAIC.nii.gz")
    
    # Copy DTI sidecar files
    bval_file = dti_file.replace('.nii.gz', '.bval')
    bvec_file = dti_file.replace('.nii.gz', '.bvec')
    json_file = dti_file.replace('.nii.gz', '.json')
    
    target_bval = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bval")
    target_bvec = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bvec")
    target_json = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.json")
    
    for source, target, name in [(bval_file, target_bval, "bval"), 
                                 (bvec_file, target_bvec, "bvec"),
                                 (json_file, target_json, "JSON")]:
        if os.path.exists(source) and not os.path.exists(target):
            shutil.copy2(source, target)
            print(f"Copied {name} file: {os.path.basename(source)} -> {os.path.basename(target)}")
        elif not os.path.exists(source) and name in ["bval", "bvec"]:
            print(f"WARNING: No {name} file found at {source}")
    
    # ADDED 7/25/2025: Copy fieldmap files if they exist
    fieldmap_patterns = [
        ("*FIELDMAP*MAG*1*.nii.gz", "FIELDMAP_MAG1.nii.gz"),
        ("*FIELDMAP*MAG*2*.nii.gz", "FIELDMAP_MAG2.nii.gz"), 
        ("*FIELDMAP*PHASE*.nii.gz", "FIELDMAP_PHASEDIFF.nii.gz"),
        ("*B0*MAP*MAG*1*.nii.gz", "FIELDMAP_MAG1.nii.gz"),
        ("*B0*MAP*MAG*2*.nii.gz", "FIELDMAP_MAG2.nii.gz"),
        ("*B0*MAP*PHASE*.nii.gz", "FIELDMAP_PHASEDIFF.nii.gz")
    ]
    
    fieldmap_found = False
    for pattern, target_name in fieldmap_patterns:
        files = glob.glob(os.path.join(nifti2_dir, pattern))
        if files:
            source_file = files[0]  # Take first match
            target_fieldmap = os.path.join(mrtrix3_inputs, target_name)
            
            if not os.path.exists(target_fieldmap):
                shutil.copy2(source_file, target_fieldmap)
                print(f"Copied fieldmap: {os.path.basename(source_file)} -> {target_name}")
                fieldmap_found = True
                
                # Copy corresponding JSON file
                json_source = source_file.replace('.nii.gz', '.json')
                json_target = target_fieldmap.replace('.nii.gz', '.json')
                if os.path.exists(json_source) and not os.path.exists(json_target):
                    shutil.copy2(json_source, json_target)
                    print(f"Copied fieldmap JSON: {os.path.basename(json_source)} -> {os.path.basename(json_target)}")
    
    if not fieldmap_found:
        print("INFO: No fieldmap files found - will use standard preprocessing without distortion correction")
    
    # Verify essential DTI files
    if not os.path.exists(target_bval) or not os.path.exists(target_bvec):
        raise FileNotFoundError("Missing essential bval or bvec files - DTI processing cannot continue")
    
    return target_dti

# ENHANCED 7/25/2025: Updated to return actual PE direction for MRtrix3 instead of dwifslpreproc format
def detect_pe_direction_from_json(dti_file):
    """Detect phase encoding direction from JSON sidecar."""
    json_file = dti_file.replace('.nii.gz', '.json')
    
    if not os.path.exists(json_file):
        print(f"WARNING: No JSON sidecar found at {json_file}")
        print("Defaulting to 'j' phase encoding direction")
        return 'j'
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        pe_dir = None
        if 'PhaseEncodingDirection' in json_data:
            pe_dir = json_data['PhaseEncodingDirection']
        elif 'InPlanePhaseEncodingDirection' in json_data:
            pe_dir = json_data['InPlanePhaseEncodingDirection']
        
        if pe_dir:
            # ENHANCED 7/25/2025: Return the actual direction for MRtrix3 (not dwifslpreproc format)
            return pe_dir
        
        print(f"WARNING: Could not interpret phase encoding direction: {pe_dir}")
        print("Defaulting to 'j' phase encoding direction")
        return 'j'
        
    except Exception as e:
        print(f"WARNING: Error reading JSON file: {e}")
        print("Defaulting to 'j' phase encoding direction")
        return 'j'

def read_dti_json(dti_file):
    """Read DTI JSON sidecar and extract relevant parameters."""
    json_file = dti_file.replace('.nii.gz', '.json')
    
    if not os.path.exists(json_file):
        print(f"WARNING: No JSON sidecar found at {json_file}")
        return {
            'TotalReadoutTime': 0.1,
            'RepetitionTime': 2.0
        }
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        readout_time = 0.1
        if 'TotalReadoutTime' in json_data:
            readout_time = json_data['TotalReadoutTime']
        elif 'EffectiveEchoSpacing' in json_data and 'ReconMatrixPE' in json_data:
            readout_time = json_data['EffectiveEchoSpacing'] * (json_data['ReconMatrixPE'] - 1)
        
        repetition_time = json_data.get('RepetitionTime', 2.0)
        
        return {
            'TotalReadoutTime': readout_time,
            'RepetitionTime': repetition_time
        }
        
    except Exception as e:
        print(f"WARNING: Error reading JSON file: {e}")
        return {
            'TotalReadoutTime': 0.1,
            'RepetitionTime': 2.0
        }

def detect_shell_configuration(dti_file):
    """Detect shell configuration from bval file."""
    bval_file = dti_file.replace('.nii.gz', '.bval')
    
    if not os.path.exists(bval_file):
        print(f"ERROR: No bval file found at {bval_file}")
        return None, None
    
    bvals = np.loadtxt(bval_file)
    bvals_rounded = np.round(bvals / 50) * 50
    unique_bvals = np.unique(bvals_rounded[bvals_rounded > 50])
    shell_count = len(unique_bvals)
    
    print(f"Detected b-values: {unique_bvals}")
    print(f"Shell count: {shell_count}")
    
    if shell_count == 1:
        if unique_bvals[0] <= 1200:
            shell_type = "single_shell_dti"
        else:
            shell_type = "single_shell_hardi"
    elif shell_count == 2:
        shell_type = "dual_shell"
    else:
        shell_type = "multi_shell"
    
    return shell_type, unique_bvals

def load_global_config(file_path):
    """Load global configuration."""
    global config
    with open(file_path, 'r') as f:
        config = json.load(f)

def detect_freesurfer_version(subject_folder):
    """Detect available FreeSurfer versions."""
    fs_dirs = {
        'freesurfer8.0': 'freesurfer8.0',
        'FreeSurfer7': 'FreeSurfer7', 
        'FreeSurfer': 'FreeSurfer'
    }
    
    available_versions = {}
    
    for version, dirname in fs_dirs.items():
        if dirname == 'freesurfer8.0':
            fs_path = os.path.join(subject_folder, dirname, os.path.basename(subject_folder))
        else:
            fs_path = os.path.join(subject_folder, dirname)

        if os.path.exists(fs_path):
            aparc_aseg = os.path.join(fs_path, 'mri', 'aparc+aseg.mgz')
            if os.path.exists(aparc_aseg):
                available_versions[version] = fs_path
    
    if not available_versions:
        return None, None, "No valid FreeSurfer reconstruction found"
    
    if 'freesurfer8.0' in available_versions:
        return 'freesurfer8.0', available_versions['freesurfer8.0'], None
    elif 'FreeSurfer7' in available_versions:
        warning = "Using FreeSurfer 7 - consider upgrading to FreeSurfer 8.0 for optimal results"
        return 'FreeSurfer7', available_versions['FreeSurfer7'], warning
    else:
        warning = "WARNING: Using FreeSurfer 5.3 - strongly recommend upgrading to FreeSurfer 7+ for better results"
        return 'FreeSurfer', available_versions['FreeSurfer'], warning

def find_freesurfer_files(fs_path, is_nhp=False):
    """Find required FreeSurfer files for connectome generation."""
    if is_nhp:
        return None
    
    files = {
        'aparc_aseg': os.path.join(fs_path, 'mri', 'aparc+aseg.mgz'),
        'aparc_dk': os.path.join(fs_path, 'mri', 'aparc.DKTatlas+aseg.mgz'),
        'aparc_destrieux': os.path.join(fs_path, 'mri', 'aparc.a2009s+aseg.mgz'),
        'orig': os.path.join(fs_path, 'mri', 'orig.mgz'),
        'brain': os.path.join(fs_path, 'mri', 'brain.mgz')
    }
    
    available_files = {}
    for key, path in files.items():
        if os.path.exists(path):
            available_files[key] = path
    
    return available_files

def select_parcellation_strategy(subject_folder, is_nhp=False):
    """Determine the best parcellation strategy based on available data."""
    if is_nhp:
        return {
            'strategy': 'template_only',
            'atlases': ['Brainnetome'],
            'freesurfer_available': False,
            'warning': None
        }
    
    fs_version, fs_path, fs_warning = detect_freesurfer_version(subject_folder)
    
    if fs_version:
        fs_files = find_freesurfer_files(fs_path)
        
        available_atlases = ['Brainnetome']
        
        if 'aparc_aseg' in fs_files:
            available_atlases.append('FreeSurfer_DK')
        if 'aparc_destrieux' in fs_files:
            available_atlases.append('FreeSurfer_Destrieux')
        if 'aparc_dk' in fs_files:
            available_atlases.append('FreeSurfer_DKT')
            
        return {
            'strategy': 'freesurfer_plus_template',
            'atlases': available_atlases,
            'freesurfer_available': True,
            'freesurfer_version': fs_version,
            'freesurfer_path': fs_path,
            'freesurfer_files': fs_files,
            'warning': fs_warning
        }
    else:
        return {
            'strategy': 'template_only',
            'atlases': ['Brainnetome'],
            'freesurfer_available': False,
            'warning': "No FreeSurfer data found - using template-based parcellation only"
        }

# ENHANCED 7/25/2025: Added fieldmap configuration detection and parameter extraction
def create_enhanced_replacements_legacy(input_path, output_path, dti_folder, subject_folder, is_nhp=False):
    """Create replacement dictionary for legacy DTI data with fieldmap support."""
    # Find DTI file
    mrtrix3_inputs = os.path.join(subject_folder, "mrtrix3_inputs")
    dti_file = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
    
    if not os.path.exists(dti_file):
        raise FileNotFoundError(f"DTI_MOSAIC.nii.gz not found at {dti_file}")
    
    # Read DTI parameters
    dti_json = read_dti_json(dti_file)
    pe_direction = detect_pe_direction_from_json(dti_file)
    shell_type, unique_bvals = detect_shell_configuration(dti_file)
    
    # ADDED 7/25/2025: Detect fieldmap configuration
    fieldmap_config = detect_fieldmap_configuration(subject_folder)
    
    # Find anatomical images
    matching_t1w_files = find_t1_image(input_path)
    matching_flair_files = find_flair_image(input_path)
    
    # Handle masks
    if is_nhp:
        matching_t1_mask_file = matching_t1w_files[0].replace('.nii', '_pre_mask.nii.gz')
    else:
        matching_brainmask_images = find_t1_brainmask_image(input_path)
        matching_t1_mask_file = matching_brainmask_images[0]

    # Handle DWI masks for humans
    if not is_nhp:
        matching_dwi_brainmask_images = find_dwi_brainmask_image(dti_folder)
        if matching_dwi_brainmask_images:
            matching_dwi_mask_file = matching_dwi_brainmask_images[0]
            print(f'Using pre-existing DWI brain mask for human processing: {matching_dwi_mask_file}')
        else:
            matching_dwi_mask_file = ''
            print('WARNING: No pre-existing DWI brain mask found - will use dwi2mask as fallback')
    else:
        matching_dwi_mask_file = ''

    # Base replacements
    replacements = {
        "INPUT": dti_folder,
        "OUTPUT": output_path,
        "ANAT": matching_t1w_files[0],
        "FLAIR": matching_flair_files[0],
        "TEMPLATE": '/templates',
        "MASK": matching_t1_mask_file,
        "DWI_MASK": matching_dwi_mask_file,
        "PIXDIM4": str(dti_json['RepetitionTime']),
        "READOUTTIME": str(dti_json['TotalReadoutTime']),
        "PE_DIR": pe_direction,
        "DTI_MOSAIC_NIFTI": os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz"),
        "DTI_MOSAIC_BVEC": os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bvec"),
        "DTI_MOSAIC_BVAL": os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bval"),
    }
    
    # ADDED 7/25/2025: Add fieldmap-specific replacements
    if fieldmap_config['available']:
        fieldmap_files = fieldmap_config['files'] 
        fieldmap_params = fieldmap_config['parameters']
        delta_te=(fieldmap_params.get('DELTA_TE', 0.00246))*1000
        
        replacements.update({
            "FIELDMAP_MAG1": fieldmap_files.get('FIELDMAP_MAG1', {}).get('nifti_path', ''),
            "FIELDMAP_MAG2": fieldmap_files.get('FIELDMAP_MAG2', {}).get('nifti_path', ''),
            "FIELDMAP_PHASEDIFF": fieldmap_files.get('FIELDMAP_PHASEDIFF', {}).get('nifti_path', ''),
            "DELTA_TE": str(delta_te),
            "FIELDMAP_AVAILABLE": "true"
        })
        print(f"✓ Fieldmap distortion correction will be applied")
        print(f"  - DELTA_TE: {str(delta_te)}")
        print(f"  - Type: {fieldmap_config['type']}")
    else:
        replacements.update({
            "FIELDMAP_MAG1": "",
            "FIELDMAP_MAG2": "",
            "FIELDMAP_PHASEDIFF": "",
            "DELTA_TE": "2.46",
            "FIELDMAP_AVAILABLE": "false"
        })
        print("⚠ No fieldmaps detected - using standard preprocessing without distortion correction")
    
    # Add FreeSurfer-specific replacements for humans
    if not is_nhp:
        parcellation_info = select_parcellation_strategy(input_path, is_nhp)
        
        if parcellation_info['freesurfer_available']:
            fs_files = parcellation_info['freesurfer_files']
            replacements.update({
                "FREESURFER_DIR": parcellation_info['freesurfer_path'],
                "FS_APARC_ASEG": fs_files.get('aparc_aseg', ''),
                "FS_APARC_DK": fs_files.get('aparc_dk', ''),
                "FS_APARC_DESTRIEUX": fs_files.get('aparc_destrieux', ''),
                "FS_BRAIN": fs_files.get('brain', ''),
                "FS_VERSION": parcellation_info['freesurfer_version']
            })
        else:
            replacements.update({
                "FREESURFER_DIR": "",
                "FS_APARC_ASEG": "",
                "FS_APARC_DK": "",
                "FS_APARC_DESTRIEUX": "",
                "FS_BRAIN": "",
                "FS_VERSION": "none"
            })
    
    # ENHANCED 7/25/2025: Return fieldmap configuration as part of the response
    return replacements, parcellation_info if not is_nhp else None, shell_type, unique_bvals, fieldmap_config

# ENHANCED 7/25/2025: Added fieldmap conditional processing logic
def load_commands_legacy(file_path, input_path, output_path, dti_folder, is_nhp=False, rerun=False):
    """Load and modify commands for legacy DTI processing with fieldmap support."""
    # Load JSON commands file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # ENHANCED 7/25/2025: Get enhanced replacements including fieldmap paths
    replacements, parcellation_info, shell_type, unique_bvals, fieldmap_config = create_enhanced_replacements_legacy(
        input_path, output_path, dti_folder, input_path, is_nhp
    )
    
    # Add subject name placeholder
    replacements['SUBJECT_NAME'] = 'PLACEHOLDER_SUBJECT'
    replacements['SPECIES'] = 'nhp' if is_nhp else 'human'
    
    print(f"\n=== DTI CONFIGURATION ===")
    print(f"Shell type: {shell_type}")
    print(f"B-values: {unique_bvals}")
    print(f"Phase encoding: {replacements['PE_DIR']}")
    print(f"Readout time: {replacements['READOUTTIME']}")
    # ADDED 7/25/2025: Log fieldmap availability
    print(f"Fieldmap available: {fieldmap_config['available']}")
    
    commands = []
    skipped_steps = []
    
    # ADDED 7/25/2025: Check if we have fieldmaps and pre-existing DWI mask
    has_fieldmaps = fieldmap_config['available']
    has_existing_dwi_mask = not is_nhp and bool(replacements.get('DWI_MASK'))
    
    # Log configuration
    if not is_nhp and parcellation_info:
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")
        
        print(f"FreeSurfer Strategy: {parcellation_info['strategy']}")
        print(f"Available Atlases: {', '.join(parcellation_info['atlases'])}")
        
        if parcellation_info['freesurfer_available']:
            print(f"FreeSurfer Version: {parcellation_info['freesurfer_version']}")
            print(f"FreeSurfer Path: {parcellation_info['freesurfer_path']}")

    # Log processing strategies
    if is_nhp:
        print("DWI Mask Strategy (NHP): Using T1w-based approach")
    elif has_existing_dwi_mask:
        print(f"DWI Mask Strategy (Human): Using pre-existing mask from {replacements['DWI_MASK']}")
    else:
        print("DWI Mask Strategy (Human): Will use dwi2mask as fallback")
    
    # ADDED 7/25/2025: Log distortion correction strategy
    if has_fieldmaps:
        print("Distortion Correction: Fieldmap-based (optimal)")
    else:
        print("Distortion Correction: None (consider acquiring fieldmaps for future scans)")

    for step in data['steps']:
        step_name = step['name']
        
        # Check if step should be run for this species
        if 'species' in step:
            if step['species'] == 'human' and is_nhp:
                skipped_steps.append(f"{step_name} (NHP - human only)")
                continue
            elif step['species'] == 'nhp' and not is_nhp:
                skipped_steps.append(f"{step_name} (Human - NHP only)")
                continue
        
        # ENHANCED 7/25/2025: Check conditional execution including fieldmap conditions
        if 'conditional' in step:
            condition = step['conditional']
            
            # Handle fieldmap conditions
            if condition == 'fieldmap_available' and not has_fieldmaps:
                skipped_steps.append(f"{step_name} (No fieldmaps available)")
                continue
            elif condition == 'no_fieldmap_fallback' and has_fieldmaps:
                skipped_steps.append(f"{step_name} (Using fieldmap version)")
                continue
            elif condition == 'skip_if_preexisting_dwi_mask' and has_existing_dwi_mask:
                skipped_steps.append(f"{step_name} (Using pre-existing DWI mask)")
                continue
        
        # Check if step requires specific FreeSurfer files (for humans)
        if not is_nhp and 'requires' in step:
            required_file = step['requires']
            if required_file not in replacements or not replacements[required_file]:
                skipped_steps.append(f"{step_name} (Missing: {required_file})")
                continue
        
        print(f"- Including step: {step_name}")
        
        # Build validation output path
        validation_output = step['validation_output']
        for placeholder, value in replacements.items():
            validation_output = validation_output.replace(placeholder, value)
        
        # Build command
        command = step['cmd']
        for placeholder, value in replacements.items():
            command = command.replace(placeholder, value)
        
        # Define output logs
        log_file = os.path.join(output_path, f"{step_name}_log.txt")
        command_with_logging = f"{command} > {log_file} 2>&1"
        
        if rerun:
            commands.append(command_with_logging)
        else:
            commands.append(f'if [ ! -f {validation_output} ]; then\n  {command_with_logging}\nfi')
    
    # Handle pre-existing DWI mask commands
    if has_existing_dwi_mask:
        dwi_mask_commands = [
            f"# Copy and convert pre-existing DWI brain mask",
            f"if [ ! -f {output_path}/mask.nii.gz ]; then",
            f"  cp {replacements['DWI_MASK']} {output_path}/mask.nii.gz > {output_path}/step8-copy_dwi_mask_log.txt 2>&1",
            f"fi",
            f"if [ ! -f {output_path}/mask.mif ]; then",
            f"  mrconvert {output_path}/mask.nii.gz {output_path}/mask.mif -force > {output_path}/step8-convert_dwi_mask_log.txt 2>&1",
            f"fi"
        ]
        
        # Find insertion point (after bias correction)
        insert_index = 0
        for i, cmd in enumerate(commands):
            if 'step8-dwibiascorrect' in cmd:
                insert_index = i + 1
                break
        
        # Insert mask commands
        for i, mask_cmd in enumerate(dwi_mask_commands):
            commands.insert(insert_index + i, mask_cmd)
    
    # Log skipped steps
    if skipped_steps:
        print(f"\nSkipped Steps:")
        for skipped in skipped_steps:
            print(f"  - {skipped}")
    
    return commands

def create_bash_script(commands, output_file):
    """Create bash script with proper environment setup."""
    with open(output_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("\n# Set up environment variables for MRtrix3 and FreeSurfer\n")
        f.write("# Fix for MRtrix3 path - explicitly set to /opt/mrtrix3 if it exists\n")
        f.write("if [ -d '/opt/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/opt/mrtrix3'\n")
        f.write("elif [ -d '/usr/local/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/usr/local/mrtrix3'\n")
        f.write("elif [ -d '/mrtrix3' ]; then\n")
        f.write("    export MRTRIX3_DIR='/mrtrix3'\n")
        f.write("else\n")
        f.write("    echo 'WARNING: MRtrix3 directory not found, using default'\n")
        f.write("    export MRTRIX3_DIR='/opt/mrtrix3'\n")
        f.write("fi\n")
        f.write("\n")
        f.write("# Set FreeSurfer path\n")
        f.write("if [ -d '/opt/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/opt/freesurfer'\n")
        f.write("elif [ -d '/usr/local/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/usr/local/freesurfer'\n")
        f.write("elif [ -d '/freesurfer' ]; then\n")
        f.write("    export FREESURFER_HOME='/freesurfer'\n")
        f.write("else\n")
        f.write("    echo 'WARNING: FreeSurfer directory not found'\n")
        f.write("    export FREESURFER_HOME='/opt/freesurfer'\n")
        f.write("fi\n")
        f.write("\n")
        f.write("echo \"Using MRTRIX3_DIR: $MRTRIX3_DIR\"\n")
        f.write("echo \"Using FREESURFER_HOME: $FREESURFER_HOME\"\n")
        f.write("\n")
        f.write("# Verify critical files exist\n")
        f.write("echo 'Checking MRtrix3 label conversion files...'\n")
        f.write("ls -la \"$MRTRIX3_DIR/share/mrtrix3/labelconvert/fs_default.txt\" 2>/dev/null || echo 'ERROR: fs_default.txt not found'\n")
        f.write("ls -la \"$MRTRIX3_DIR/share/mrtrix3/labelconvert/fs_a2009s.txt\" 2>/dev/null || echo 'ERROR: fs_a2009s.txt not found'\n")
        f.write("ls -la \"$FREESURFER_HOME/FreeSurferColorLUT.txt\" 2>/dev/null || echo 'WARNING: FreeSurferColorLUT.txt not found'\n")
        f.write("\n")
        for command in commands:
            f.write(command)
            f.write("\n")
            
    return output_file

def create_skullstrip_command(input_image, is_nhp):
    """Create skull stripping command."""
    if is_nhp:
        model_path = "/UNet_Model/models/Site-All-T-epoch_36.model"
        output_dir = os.path.dirname(input_image)
        command = f"python3 /UNet_Model/muSkullStrip.py -in {input_image} -model {model_path} -out {output_dir}"
    else: 
        print("Human image processing uses dwi2mask fsl in pipeline")
        return False
    
    return command

# ENHANCED 7/25/2025: Added fieldmap detection to the test function
def test_dti_detection(subject_folder):
    """Standalone test function to debug DTI directory detection."""
    print(f"=== DTI DIRECTORY DETECTION TEST ===")
    print(f"Subject folder: {subject_folder}")
    
    if not os.path.exists(subject_folder):
        print("ERROR: Subject folder does not exist!")
        return
    
    try:
        all_dirs = [d for d in os.listdir(subject_folder) if os.path.isdir(os.path.join(subject_folder, d))]
        print(f"All directories found: {sorted(all_dirs)}")
    except Exception as e:
        print(f"ERROR: Cannot list directories: {e}")
        return
    
    tmp_dir = os.path.join(subject_folder, "tmp")
    if os.path.exists(tmp_dir):
        print(f"✓ tmp directory exists at subject root")
        try:
            tmp_files = os.listdir(tmp_dir)
            dicom_files = [f for f in tmp_files if f.lower().endswith(('.dcm', '.ima', '.dicom')) or not '.' in f]
            print(f"✓ Found {len(dicom_files)} potential DICOM files in tmp/")
            if tmp_files:
                print(f"Sample files: {tmp_files[:5]}")
        except Exception as e:
            print(f"ERROR: Cannot list tmp directory: {e}")
    else:
        print(f"✗ tmp directory NOT found at subject root: {tmp_dir}")
    
    dti_folder, dti_dirname = find_dti_directory(subject_folder)
    
    if dti_folder:
        print(f"SUCCESS: Found DTI directory: {dti_dirname}")
        print(f"Full path: {dti_folder}")
        
        # ADDED 7/25/2025: Test fieldmap detection
        print(f"\n=== FIELDMAP DETECTION TEST ===")
        fieldmap_config = detect_fieldmap_configuration(subject_folder)
        if fieldmap_config['available']:
            print(f"✓ Fieldmaps detected: {fieldmap_config['type']}")
            for key, file_info in fieldmap_config['files'].items():
                print(f"  - {key}: {os.path.basename(file_info['nifti_path'])}")
            print(f"  - DELTA_TE: {fieldmap_config['parameters']['DELTA_TE']:.6f}s")
        else:
            print("⚠ No fieldmaps detected")
        
        nifti2_dir = os.path.join(dti_folder, "nifti2")
        if os.path.exists(nifti2_dir):
            print(f"✓ nifti2 directory exists")
            try:
                nifti_files = [f for f in os.listdir(nifti2_dir) if f.endswith('.nii.gz')]
                print(f"✓ Found {len(nifti_files)} NIFTI files in nifti2/")
                if nifti_files:
                    print(f"NIFTI files: {nifti_files}")
            except Exception as e:
                print(f"ERROR: Cannot list nifti2 directory: {e}")
        else:
            print(f"⚠ nifti2 directory not found (DICOMs not yet converted)")
        
        mrtrix_inputs = os.path.join(dti_folder, "mrtrix3_inputs")
        if os.path.exists(mrtrix_inputs):
            print(f"✓ mrtrix3_inputs directory exists")
            try:
                files = os.listdir(mrtrix_inputs)
                print(f"Files in mrtrix3_inputs: {sorted(files)}")
            except Exception as e:
                print(f"ERROR: Cannot list mrtrix3_inputs: {e}")
        else:
            print(f"⚠ mrtrix3_inputs directory not found (will be created by pipeline)")
            
    else:
        print("FAILED: No DTI directory found")

# ENHANCED 7/25/2025: Updated main function with fieldmap support messaging
def main():
    """Main function for legacy DTI pipeline with fieldmap support."""
    parser = argparse.ArgumentParser(description='Generate SLURM batch files for legacy DTI data with fieldmap support.')
    parser.add_argument('subject_name', type=str, nargs='?', help='Name of the subject')
    parser.add_argument('subject_folder', type=str, nargs='?', help='Path to the subject folder')
    parser.add_argument('config_file', type=str, nargs='?', help='Path to the config json file')
    parser.add_argument('command_file', type=str, nargs='?', help='Path to the DTI command json file')
    parser.add_argument('-o','--output', type=str, 
                        help='Path to the output folder', 
                        default="output",
                        required=False)
    parser.add_argument('-r','--rerun', type=bool, 
                        help='Force rerun of all steps', 
                        default=False,
                        required=False)
    parser.add_argument('--test', type=str, 
                        help='Test DTI directory detection on given subject folder', 
                        required=False)
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--nhp', dest='nhp', action='store_true', 
                       help='Use non-human primate model')
    group.add_argument('--human', dest='human', action='store_true', 
                       help='Use human model (default)')
    
    args = parser.parse_args()

    if args.test:
        test_dti_detection(args.test)
        return

    if not all([args.subject_name, args.subject_folder, args.config_file, args.command_file]):
        parser.error("subject_name, subject_folder, config_file, and command_file are required for normal operation")

    if not (args.nhp or args.human):
        args.human = True

    if args.nhp == True:
        args.human = False
    
    if args.human == True:
        args.nhp = False

    if args.nhp and args.human:
        print("ERROR: Both --nhp and --human flags cannot be set simultaneously.")
        return

    print(f"Subject: {args.subject_name}")
    print(f"Species Selected: {'Non-Human Primate' if args.nhp else 'Human'}")
    # ENHANCED 7/25/2025: Updated pipeline description
    print(f"Pipeline Type: Legacy DTI Processing with Fieldmap Support")
    
    # Find DTI directory
    print("\n=== DTI DIRECTORY DETECTION ===")
    dti_folder, dti_dirname = find_dti_directory(args.subject_folder)
    if not dti_folder:
        print("ERROR: DTI directory not found")
        all_dirs = [d for d in os.listdir(args.subject_folder) if os.path.isdir(os.path.join(args.subject_folder, d))]
        for d in sorted(all_dirs):
            print(f"  - {d}")
        exit(1)
    
    print(f"Using DTI directory: {dti_dirname}")
        
    # Create output directories   
    output_path = os.path.join(dti_folder, "mrtrix3_outputs")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    load_global_config(args.config_file)
    
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    if not os.path.exists(scripts_dir):
        print(f"Creating scripts directory at {scripts_dir}")
        os.makedirs(scripts_dir, exist_ok=True)
    
    # DICOM to NIFTI conversion
    print("\n=== DICOM TO NIFTI CONVERSION ===")
    
    tmp_dir = os.path.join(args.subject_folder, 'tmp')
    if not os.path.exists(tmp_dir):
        print(f"ERROR: tmp directory not found at {tmp_dir}")
        print("Legacy DTI data should have raw DICOMs in tmp/ directory at subject root")
        exit(1)
    
    try:
        tmp_files = os.listdir(tmp_dir)
        dicom_files = [f for f in tmp_files if f.lower().endswith(('.dcm', '.ima', '.dicom')) or not '.' in f]
        if not dicom_files:
            print(f"ERROR: No DICOM files found in {tmp_dir}")
            print(f"Found files: {tmp_files[:10]}...")
            exit(1)
        print(f"Found {len(dicom_files)} DICOM files in tmp/")
    except Exception as e:
        print(f"ERROR: Cannot access tmp directory: {e}")
        exit(1)
    
    print("Converting DICOMs to NIFTI using ImageTypeChecker...")
    try:
        checker = ImageTypeChecker(args.subject_folder, args.config_file)
        print("✓ DICOM to NIFTI conversion completed")
        
        # ADDED 7/25/2025: Check if fieldmaps were detected
        fieldmap_summary = checker.get_fieldmap_summary()
        if fieldmap_summary:
            print("✓ Fieldmap images detected during conversion:")
            for label, info in fieldmap_summary.items():
                print(f"  - {label}: TE={info['echo_time']:.6f}s")
        else:
            print("ℹ No fieldmap images detected during conversion")
        
    except Exception as e:
        print(f"ERROR: DICOM conversion failed: {e}")
        exit(1)
    
    # Create mrtrix3_inputs
    print("\n=== CREATING MRTRIX3 INPUTS ===")
    try:
        target_dti_file = create_mrtrix3_inputs_from_nifti2(dti_folder, args.subject_folder)
        print("✓ mrtrix3_inputs created successfully")
    except Exception as e:
        print(f"ERROR: Failed to create mrtrix3_inputs: {e}")
        exit(1)
    
    # ENHANCED 7/25/2025: Analyze DTI and fieldmap configuration
    print("\n=== DTI & FIELDMAP CONFIGURATION ANALYSIS ===")
    
    try:
        mrtrix3_inputs = os.path.join(args.subject_folder, "mrtrix3_inputs")
        dti_file = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
        
        if not os.path.exists(dti_file):
            print(f"ERROR: DTI_MOSAIC.nii.gz not found at {dti_file}")
            exit(1)
            
        shell_type, unique_bvals = detect_shell_configuration(dti_file)
        print(f"DTI Configuration: {shell_type}")
        print(f"B-values: {unique_bvals}")
        
        # ADDED 7/25/2025: Detect fieldmap configuration
        fieldmap_config = detect_fieldmap_configuration(args.subject_folder)
        
        if shell_type not in ['single_shell_dti', 'single_shell_hardi']:
            print(f"WARNING: This pipeline is optimized for single-shell DTI, but detected {shell_type}")
            print("Consider using the multi-shell pipeline instead")
            
    except Exception as e:
        print(f"ERROR: Failed to analyze DTI data: {e}")
        exit(1)
    
    # Check for DWI brain mask (humans only)
    print("\n=== DWI BRAIN MASK ANALYSIS ===")
    if not args.nhp:
        dwi_mask_files = find_dwi_brainmask_image(dti_folder)
        if dwi_mask_files:
            print(f"Found pre-existing DWI brain mask: {dwi_mask_files[0]}")
        else:
            print("No pre-existing DWI brain mask found - will use dwi2mask")
    else:
        print("NHP processing: Using T1w-based mask approach")
        dwi_mask_files = []
    
    # Analyze FreeSurfer availability (humans only)
    if not args.nhp:
        print("\n=== FREESURFER ANALYSIS ===")
        parcellation_info = select_parcellation_strategy(args.subject_folder, args.nhp)
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")

    # Build skull-stripping command
    input_t1 = find_t1_image(args.subject_folder)
    skull_strip_cmd = create_skullstrip_command(input_t1[0], args.nhp)
        
    # Load commands
    print("\n=== BUILDING COMMAND LIST ===")
    commands = load_commands_legacy(args.command_file, args.subject_folder, output_path, dti_folder, args.nhp, args.rerun)
    
    # Replace subject name placeholder
    commands = [cmd.replace('PLACEHOLDER_SUBJECT', args.subject_name) for cmd in commands]
    
    # Add final reporting
    species_flag = 'nhp' if args.nhp else 'human'
    fs_version = 'none'
    
    if not args.nhp:
        parcellation_info = select_parcellation_strategy(args.subject_folder, args.nhp)
        if parcellation_info['freesurfer_available']:
            fs_version = parcellation_info['freesurfer_version']
    
    # ENHANCED 7/25/2025: Updated reporting command to include fieldmap information
    reporting_cmd = f"""
# Generate standardized report
python3 /scripts/generate_standardized_report.py \\
    --subject {args.subject_name} \\
    --output_dir {output_path} \\
    --species {species_flag} \\
    --freesurfer_version {fs_version} \\
    --pipeline_type legacy_dti_fieldmap \\
    --fieldmap_available {fieldmap_config['available']} \\
    > {output_path}/reporting_log.txt 2>&1
"""
    commands.append(reporting_cmd)
    
    # Create batch script
    print("\n=== CREATING BATCH SCRIPT ===")
    batch_script = create_bash_script(commands, os.path.join(output_path, f"{args.subject_name}_dti_script.sh"))
    
    # Create SLURM batch file
    slurm_creator = SLURMFileCreator(args.subject_name, config)
    slurm_creator.create_bind_string(args.subject_folder)
    slurm_creator.create_batch_file(batch_script, args.nhp, skull_strip_cmd)
    
    # ENHANCED 7/25/2025: Updated final summary with fieldmap information
    print(f"\n=== ENHANCED LEGACY DTI PIPELINE PREPARATION COMPLETE ===")
    print(f"Subject: {args.subject_name}")
    print(f"Species: {'NHP' if args.nhp else 'Human'}")
    print(f"Pipeline: Legacy Single-Shell DTI with Fieldmap Support")
    print(f"DTI Directory: {dti_dirname}")
    print(f"Shell Type: {shell_type}")
    print(f"B-values: {unique_bvals}")
    print(f"Fieldmap Available: {'Yes' if fieldmap_config['available'] else 'No'}")
    if fieldmap_config['available']:
        print(f"Fieldmap Type: {fieldmap_config['type']}")
        print(f"DELTA_TE: {fieldmap_config['parameters']['DELTA_TE']*1000:.6f}s")
    print(f"Output Directory: {output_path}")
    print(f"Total Commands: {len(commands)}")
    
    if not args.nhp and dwi_mask_files:
        print(f"DWI Mask: Using pre-existing mask")
    elif not args.nhp:
        print("DWI Mask: Will generate using dwi2mask")
    else:
        print("DWI Mask: Using T1w-based approach")
    
    if not args.nhp:
        print(f"FreeSurfer Version: {fs_version}")
    
    print(f"Batch Script: {batch_script}")
    print(f"Ready for SLURM submission!")

if __name__ == "__main__":
    main()