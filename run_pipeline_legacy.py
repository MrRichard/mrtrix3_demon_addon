import argparse
from SlurmBatch import SLURMFileCreator
from ImageTypeChecker import ImageTypeChecker
import glob
import json
import os
import logging
import numpy as np

def find_t1_image(input_path):
    """Find T1 anatomical file."""
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-tfl3d116*.info')
    matching_files = glob.glob(pattern)
    
    # Replace the suffix ".info" with ".nii" for each matching file
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_t1_brainmask_image(input_path):
    """Find T1 brain mask file."""
    pattern = os.path.join(os.path.join(input_path,'nifti','cat12'), '*tfl3d116*_bet_mask.nii.gz')
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
        'DTI_S*',      # DTI_S0006, DTI_S0012, etc.
        'DTI*',        # DTI, DTI_1, etc.
        'DWI_S*',      # Alternative naming
        'DWI*',        # Alternative naming
        'DIFFUSION_S*', # Another alternative
        'DIFFUSION*'   # Another alternative
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
        # Fallback: look for any directory containing DTI/DWI/DIFFUSION
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
    
    # Remove duplicates
    dti_dirs = list(set(dti_dirs))
    
    # Check for tmp/ directory at subject root level (not in DTI directory)
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
        # Sort by name and take the first one
        dti_dirs.sort()
        selected_dir = dti_dirs[0]
        print(f"Selected: {os.path.basename(selected_dir)}")
    else:
        selected_dir = dti_dirs[0]
        print(f"Found DTI directory: {os.path.basename(selected_dir)}")
    
    return selected_dir, os.path.basename(selected_dir)

def find_dwi_brainmask_image(dti_folder):
    """
    Find pre-existing diffusion brain mask (*epb51_T2_mask.nii) in the DTI folder.
    This is used for HUMAN processing only. NHP processing uses T1w-based masks.
    """
    pattern = os.path.join(dti_folder, '*epb51_T2_mask.nii')
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        pattern_gz = os.path.join(dti_folder, '*epb51_T2_mask.nii.gz')
        matching_files = glob.glob(pattern_gz)
    
    if matching_files:
        print(f"Found pre-existing DWI brain mask: {matching_files[0]}")
        return matching_files
    else:
        print(f"WARNING: No pre-existing DWI brain mask found in {dti_folder}")
        print("Expected pattern: *epb51_T2_mask.nii or *epb51_T2_mask.nii.gz")
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
    """
    Find DTI MOSAIC file in the nifti2 directory within the DTI folder.
    For legacy DTI data, we look in nifti2/ which is created from DICOMs.
    """
    nifti2_dir = os.path.join(subject_folder, "nifti2")
    
    if not os.path.exists(nifti2_dir):
        print(f"ERROR: nifti2 directory not found at {nifti2_dir}")
        print("Run DICOM conversion first using ImageTypeChecker")
        return None
    
    # Look for DTI files - try different naming patterns
    patterns = [
        "*DTI*.nii.gz",
        "*dti*.nii.gz", 
        "*ep2d_diff*.nii.gz",  # Common Siemens DTI sequence name
        "*DIFFUSION*.nii.gz",
        "*diff*.nii.gz",
        "*dwi*.nii.gz",         # Alternative naming
        "*MOSAIC*.nii.gz"       # Generic MOSAIC naming
    ]
    
    dti_files = []
    for pattern in patterns:
        files = glob.glob(os.path.join(nifti2_dir, pattern))
        # Filter out obvious non-DTI files
        files = [f for f in files if 'PHASE' not in f and 'SBREF' not in f and 'fieldmap' not in f.lower()]
        dti_files.extend(files)
        if files:
            print(f"DEBUG: Pattern {pattern} found: {[os.path.basename(f) for f in files]}")
    
    if not dti_files:
        # Fallback: look for any .nii.gz file that's not obviously something else
        all_files = glob.glob(os.path.join(nifti2_dir, "*.nii.gz"))
        dti_files = [f for f in all_files if 'PHASE' not in f and 'SBREF' not in f and 'fieldmap' not in f.lower()]
        
        if dti_files:
            print(f"WARNING: No explicit DTI files found. Using: {[os.path.basename(f) for f in dti_files]}")
        else:
            print("ERROR: No suitable DTI files found in nifti2 directory")
            print(f"Available files: {os.listdir(nifti2_dir) if os.path.exists(nifti2_dir) else 'none'}")
            return None
    
    # If multiple files, pick the largest (likely the main DTI acquisition)
    if len(dti_files) > 1:
        file_sizes = {f: os.path.getsize(f) for f in dti_files}
        largest_file = max(file_sizes, key=file_sizes.get)
        print(f"Multiple DTI files found. Selected largest: {os.path.basename(largest_file)}")
        return largest_file
    else:
        print(f"Found DTI file: {os.path.basename(dti_files[0])}")
        return dti_files[0]

def create_mrtrix3_inputs_from_nifti2(dti_folder, subject_folder):
    """
    Create mrtrix3_inputs directory and copy/process files from nifti2.
    This mimics the workflow from the original pipeline.
    """
    nifti2_dir = os.path.join(dti_folder, "nifti2")
    mrtrix3_inputs = os.path.join(dti_folder, "mrtrix3_inputs")
    
    if not os.path.exists(nifti2_dir):
        raise FileNotFoundError(f"nifti2 directory not found: {nifti2_dir}")
    
    # Create mrtrix3_inputs directory
    if not os.path.exists(mrtrix3_inputs):
        os.makedirs(mrtrix3_inputs)
        print(f"Created mrtrix3_inputs directory: {mrtrix3_inputs}")
    
    # Find DTI file in nifti2
    dti_file = find_dti_mosaic(dti_folder, subject_folder)
    if not dti_file:
        raise FileNotFoundError("No DTI file found in nifti2 directory")
    
    # Get base name for consistent naming
    base_name = os.path.basename(dti_file).replace('.nii.gz', '')
    
    # Copy DTI files to mrtrix3_inputs with standardized naming
    import shutil
    
    # Main DTI file
    target_dti = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
    if not os.path.exists(target_dti):
        shutil.copy2(dti_file, target_dti)
        print(f"Copied DTI file: {os.path.basename(dti_file)} -> DTI_MOSAIC.nii.gz")
    
    # Look for corresponding bval and bvec files
    bval_file = dti_file.replace('.nii.gz', '.bval')
    bvec_file = dti_file.replace('.nii.gz', '.bvec')
    json_file = dti_file.replace('.nii.gz', '.json')
    
    target_bval = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bval")
    target_bvec = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.bvec")
    target_json = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.json")
    
    # Copy bval file
    if os.path.exists(bval_file) and not os.path.exists(target_bval):
        shutil.copy2(bval_file, target_bval)
        print(f"Copied bval file: {os.path.basename(bval_file)} -> DTI_MOSAIC.bval")
    elif not os.path.exists(bval_file):
        print(f"WARNING: No bval file found at {bval_file}")
    
    # Copy bvec file
    if os.path.exists(bvec_file) and not os.path.exists(target_bvec):
        shutil.copy2(bvec_file, target_bvec)
        print(f"Copied bvec file: {os.path.basename(bvec_file)} -> DTI_MOSAIC.bvec")
    elif not os.path.exists(bvec_file):
        print(f"WARNING: No bvec file found at {bvec_file}")
    
    # Copy JSON file if available
    if os.path.exists(json_file) and not os.path.exists(target_json):
        shutil.copy2(json_file, target_json)
        print(f"Copied JSON file: {os.path.basename(json_file)} -> DTI_MOSAIC.json")
    elif not os.path.exists(json_file):
        print(f"INFO: No JSON file found at {json_file}")
    
    # Verify that we have the essential files
    if not os.path.exists(target_bval) or not os.path.exists(target_bvec):
        raise FileNotFoundError("Missing essential bval or bvec files - DTI processing cannot continue")
    
    return target_dti

def detect_pe_direction_from_json(dti_file):
    """
    Detect phase encoding direction from JSON sidecar.
    Returns the PE direction code for dwifslpreproc.
    """
    json_file = dti_file.replace('.nii.gz', '.json')
    
    if not os.path.exists(json_file):
        print(f"WARNING: No JSON sidecar found at {json_file}")
        print("Defaulting to 'ap' phase encoding direction")
        return 'ap'
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        # Look for phase encoding direction
        pe_dir = None
        if 'PhaseEncodingDirection' in json_data:
            pe_dir = json_data['PhaseEncodingDirection']
        elif 'InPlanePhaseEncodingDirection' in json_data:
            pe_dir = json_data['InPlanePhaseEncodingDirection']
        
        if pe_dir:
            # Convert to dwifslpreproc format
            if pe_dir in ['j', 'j-', 'AP', 'A>>P']:
                return 'ap'
            elif pe_dir in ['j+', 'PA', 'P>>A']:
                return 'pa'
            elif pe_dir in ['i', 'i-', 'LR', 'L>>R']:
                return 'lr'
            elif pe_dir in ['i+', 'RL', 'R>>L']:
                return 'rl'
        
        print(f"WARNING: Could not interpret phase encoding direction: {pe_dir}")
        print("Defaulting to 'ap' phase encoding direction")
        return 'ap'
        
    except Exception as e:
        print(f"WARNING: Error reading JSON file: {e}")
        print("Defaulting to 'ap' phase encoding direction")
        return 'ap'

def read_dti_json(dti_file):
    """Read DTI JSON sidecar and extract relevant parameters."""
    json_file = dti_file.replace('.nii.gz', '.json')
    
    if not os.path.exists(json_file):
        print(f"WARNING: No JSON sidecar found at {json_file}")
        return {
            'TotalReadoutTime': 0.1,  # Default fallback
            'RepetitionTime': 2.0     # Default fallback
        }
    
    try:
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        # Extract readout time
        readout_time = 0.1  # Default
        if 'TotalReadoutTime' in json_data:
            readout_time = json_data['TotalReadoutTime']
        elif 'EffectiveEchoSpacing' in json_data and 'ReconMatrixPE' in json_data:
            # Calculate from EES and matrix size
            readout_time = json_data['EffectiveEchoSpacing'] * (json_data['ReconMatrixPE'] - 1)
        
        # Extract repetition time
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
    """
    Detect shell configuration from bval file.
    Returns shell type and b-values.
    """
    bval_file = dti_file.replace('.nii.gz', '.bval')
    
    if not os.path.exists(bval_file):
        print(f"ERROR: No bval file found at {bval_file}")
        return None, None
    
    # Read b-values
    bvals = np.loadtxt(bval_file)
    
    # Round to nearest 50 to account for scanner variations
    bvals_rounded = np.round(bvals / 50) * 50
    
    # Find unique non-zero b-values
    unique_bvals = np.unique(bvals_rounded[bvals_rounded > 50])
    shell_count = len(unique_bvals)
    
    print(f"Detected b-values: {unique_bvals}")
    print(f"Shell count: {shell_count}")
    
    # Classify shell configuration
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

def create_enhanced_replacements_legacy(input_path, output_path, dti_folder, is_nhp=False):
    """
    Create replacement dictionary for legacy DTI data.
    """
    # Find DTI file (now standardized as DTI_MOSAIC.nii.gz in mrtrix3_inputs)
    mrtrix3_inputs = os.path.join(dti_folder, "mrtrix3_inputs")
    dti_file = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
    
    if not os.path.exists(dti_file):
        raise FileNotFoundError(f"DTI_MOSAIC.nii.gz not found at {dti_file}")
    
    # Read DTI parameters
    dti_json = read_dti_json(dti_file)
    pe_direction = detect_pe_direction_from_json(dti_file)
    shell_type, unique_bvals = detect_shell_configuration(dti_file)
    
    # Find anatomical images
    matching_t1w_files = find_t1_image(input_path)
    matching_flair_files = find_flair_image(input_path)
    
    # Handle masks
    if is_nhp:
        matching_t1_mask_file = matching_t1w_files[0].replace('.nii', '_pre_mask.nii.gz')
    else:
        matching_brainmask_images = find_t1_brainmask_image(input_path)
        matching_t1_mask_file = matching_brainmask_images[0]

    # Handle DWI masks for humans - pass DTI folder instead of input_path
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

    # Base replacements (note: INPUT now points to the DTI folder's mrtrix3_inputs)
    replacements = {
        "INPUT": dti_folder,  # Changed: now points to DTI folder
        "OUTPUT": output_path,
        "ANAT": matching_t1w_files[0],
        "FLAIR": matching_flair_files[0],
        "TEMPLATE": '/templates',
        "MASK": matching_t1_mask_file,
        "DWI_MASK": matching_dwi_mask_file,
        "PIXDIM4": str(dti_json['RepetitionTime']),
        "READOUTTIME": str(dti_json['TotalReadoutTime']),
        "DTI_MOSAIC": dti_file,  # Standardized DTI file path
        "PE_DIR": pe_direction
    }
    
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
    
    return replacements, parcellation_info if not is_nhp else None, shell_type, unique_bvals

def load_commands_legacy(file_path, input_path, output_path, dti_folder, is_nhp=False, rerun=False):
    """
    Load and modify commands for legacy DTI processing.
    """
    # Load JSON commands file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Get enhanced replacements including FreeSurfer paths
    replacements, parcellation_info, shell_type, unique_bvals = create_enhanced_replacements_legacy(
        input_path, output_path, dti_folder, is_nhp
    )
    
    # Add subject name placeholder
    replacements['SUBJECT_NAME'] = 'PLACEHOLDER_SUBJECT'
    replacements['SPECIES'] = 'nhp' if is_nhp else 'human'
    
    print(f"\n=== DTI CONFIGURATION ===")
    print(f"Shell type: {shell_type}")
    print(f"B-values: {unique_bvals}")
    print(f"Phase encoding: {replacements['PE_DIR']}")
    print(f"Readout time: {replacements['READOUTTIME']}")
    
    commands = []
    skipped_steps = []
    
    # Check if we have a pre-existing DWI mask (only for humans)
    has_existing_dwi_mask = not is_nhp and bool(replacements.get('DWI_MASK'))
    
    # Log FreeSurfer information for humans
    if not is_nhp and parcellation_info:
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")
        
        print(f"FreeSurfer Strategy: {parcellation_info['strategy']}")
        print(f"Available Atlases: {', '.join(parcellation_info['atlases'])}")
        
        if parcellation_info['freesurfer_available']:
            print(f"FreeSurfer Version: {parcellation_info['freesurfer_version']}")
            print(f"FreeSurfer Path: {parcellation_info['freesurfer_path']}")

    # Log DWI mask strategy
    if is_nhp:
        print("DWI Mask Strategy (NHP): Using T1w-based approach")
    elif has_existing_dwi_mask:
        print(f"DWI Mask Strategy (Human): Using pre-existing mask from {replacements['DWI_MASK']}")
    else:
        print("DWI Mask Strategy (Human): Will use dwi2mask as fallback")

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
        
        # Check if step requires specific FreeSurfer files (for humans)
        if not is_nhp and 'requires' in step:
            required_file = step['requires']
            if required_file not in replacements or not replacements[required_file]:
                skipped_steps.append(f"{step_name} (Missing: {required_file})")
                continue
        
        # Special handling for dwi2mask step when we have pre-existing mask (humans only)
        if step_name == 'step8-dwi2mask' and has_existing_dwi_mask:
            skipped_steps.append(f"{step_name} (Using pre-existing DWI mask for human)")
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
    
    # If we have a pre-existing DWI mask, add command to copy and convert it
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
        
        # Find the index where we should insert these commands (after step 7)
        insert_index = 0
        for i, cmd in enumerate(commands):
            if 'step7-dwibiascorrect' in cmd:
                insert_index = i + 1
                break
        
        # Insert the mask commands
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

def test_dti_detection(subject_folder):
    """
    Standalone test function to debug DTI directory detection.
    Usage: python run_pipeline_legacy.py --test /path/to/subject
    """
    print(f"=== DTI DIRECTORY DETECTION TEST ===")
    print(f"Subject folder: {subject_folder}")
    
    if not os.path.exists(subject_folder):
        print("ERROR: Subject folder does not exist!")
        return
    
    # List all directories in subject folder
    try:
        all_dirs = [d for d in os.listdir(subject_folder) if os.path.isdir(os.path.join(subject_folder, d))]
        print(f"All directories found: {sorted(all_dirs)}")
    except Exception as e:
        print(f"ERROR: Cannot list directories: {e}")
        return
    
    # Check for tmp directory at subject root level
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
    
    # Test the find_dti_directory function
    dti_folder, dti_dirname = find_dti_directory(subject_folder)
    
    if dti_folder:
        print(f"SUCCESS: Found DTI directory: {dti_dirname}")
        print(f"Full path: {dti_folder}")
        
        # Check for nifti2 directory (if DICOMs have been converted)
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
        
        # Check for mrtrix3_inputs (if files have been processed)
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

def main():
    """Main function for legacy DTI pipeline."""
    parser = argparse.ArgumentParser(description='Generate SLURM batch files for legacy DTI data.')
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
    
    # Mutually exclusive group for species selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--nhp', dest='nhp', action='store_true', 
                       help='Use non-human primate model')
    group.add_argument('--human', dest='human', action='store_true', 
                       help='Use human model (default)')
    
    args = parser.parse_args()

    # Handle test mode
    if args.test:
        test_dti_detection(args.test)
        return

    # Check required arguments for normal operation
    if not all([args.subject_name, args.subject_folder, args.config_file, args.command_file]):
        parser.error("subject_name, subject_folder, config_file, and command_file are required for normal operation")

    # Set default to human if neither is selected
    if not (args.nhp or args.human):
        args.human = True

    if args.nhp == True:
        args.human = False
    
    if args.human == True:
        args.nhp = False

    # Additional logic to ensure no conflicting state
    if args.nhp and args.human:
        print("ERROR: Both --nhp and --human flags cannot be set simultaneously.")
        return

    print(f"Subject: {args.subject_name}")
    print(f"Species Selected: {'Non-Human Primate' if args.nhp else 'Human'}")
    print(f"Pipeline Type: Legacy DTI Processing")
    
    # Find DTI directory (handles variable series numbers like DTI_S0006)
    print("\n=== DTI DIRECTORY DETECTION ===")
    dti_folder, dti_dirname = find_dti_directory(args.subject_folder)
    if not dti_folder:
        print("ERROR: DTI directory not found")
        # Show debug info
        print("Available directories:")
        all_dirs = [d for d in os.listdir(args.subject_folder) if os.path.isdir(os.path.join(args.subject_folder, d))]
        for d in sorted(all_dirs):
            print(f"  - {d}")
        exit(1)
    
    print(f"Using DTI directory: {dti_dirname}")
        
    # Create output directories   
    output_path = os.path.join(dti_folder, "mrtrix3_outputs")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load config options into global var space        
    load_global_config(args.config_file)
    
    # Ensure scripts directory exists
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    if not os.path.exists(scripts_dir):
        print(f"Creating scripts directory at {scripts_dir}")
        os.makedirs(scripts_dir, exist_ok=True)
    
    # Build the mrtrix3 input files from DICOMs (following original pipeline pattern)
    print("\n=== DICOM TO NIFTI CONVERSION ===")
    
    # Check if tmp directory with DICOMs exists at subject root level
    tmp_dir = os.path.join(args.subject_folder, 'tmp')
    if not os.path.exists(tmp_dir):
        print(f"ERROR: tmp directory not found at {tmp_dir}")
        print("Legacy DTI data should have raw DICOMs in tmp/ directory at subject root")
        exit(1)
    
    # Check if DICOMs exist in tmp
    try:
        tmp_files = os.listdir(tmp_dir)
        dicom_files = [f for f in tmp_files if f.lower().endswith(('.dcm', '.ima', '.dicom')) or not '.' in f]
        if not dicom_files:
            print(f"ERROR: No DICOM files found in {tmp_dir}")
            print(f"Found files: {tmp_files[:10]}...")  # Show first 10 files
            exit(1)
        print(f"Found {len(dicom_files)} DICOM files in tmp/")
    except Exception as e:
        print(f"ERROR: Cannot access tmp directory: {e}")
        exit(1)
    
    # Use ImageTypeChecker to convert DICOMs to NIFTI (like original pipeline)
    print("Converting DICOMs to NIFTI using ImageTypeChecker...")
    try:
        # ImageTypeChecker processes the subject folder and creates nifti2/ in appropriate subdirectories
        checker = ImageTypeChecker(args.subject_folder, args.config_file)
        print("✓ DICOM to NIFTI conversion completed")
        
    except Exception as e:
        print(f"ERROR: DICOM conversion failed: {e}")
        exit(1)
    
    # Create mrtrix3_inputs from nifti2 files
    print("\n=== CREATING MRTRIX3 INPUTS ===")
    try:
        target_dti_file = create_mrtrix3_inputs_from_nifti2(dti_folder, args.subject_folder)
        print("✓ mrtrix3_inputs created successfully")
    except Exception as e:
        print(f"ERROR: Failed to create mrtrix3_inputs: {e}")
        exit(1)
    
    # Analyze DTI configuration
    print("\n=== DTI CONFIGURATION ANALYSIS ===")
    
    # Find and analyze DTI file (now standardized as DTI_MOSAIC.nii.gz)
    try:
        mrtrix3_inputs = os.path.join(dti_folder, "mrtrix3_inputs")
        dti_file = os.path.join(mrtrix3_inputs, "DTI_MOSAIC.nii.gz")
        
        if not os.path.exists(dti_file):
            print(f"ERROR: DTI_MOSAIC.nii.gz not found at {dti_file}")
            exit(1)
            
        shell_type, unique_bvals = detect_shell_configuration(dti_file)
        print(f"DTI Configuration: {shell_type}")
        print(f"B-values: {unique_bvals}")
        
        if shell_type not in ['single_shell_dti', 'single_shell_hardi']:
            print(f"WARNING: This pipeline is optimized for single-shell DTI, but detected {shell_type}")
            print("Consider using the multi-shell pipeline instead")
            
    except Exception as e:
        print(f"ERROR: Failed to analyze DTI data: {e}")
        exit(1)
    
    # Check for DWI brain mask (humans only) - now uses dti_folder
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
    
    # For humans, analyze FreeSurfer availability
    if not args.nhp:
        print("\n=== FREESURFER ANALYSIS ===")
        parcellation_info = select_parcellation_strategy(args.subject_folder, args.nhp)
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")

    # Build skull-stripping command
    input_t1 = find_t1_image(args.subject_folder)
    skull_strip_cmd = create_skullstrip_command(input_t1[0], args.nhp)
        
    # Load commands and convert to a list - now passes dti_folder
    print("\n=== BUILDING COMMAND LIST ===")
    commands = load_commands_legacy(args.command_file, args.subject_folder, output_path, dti_folder, args.nhp, args.rerun)
    
    # Replace PLACEHOLDER_SUBJECT with actual subject name
    commands = [cmd.replace('PLACEHOLDER_SUBJECT', args.subject_name) for cmd in commands]
    
    # Add final reporting command
    species_flag = 'nhp' if args.nhp else 'human'
    fs_version = 'none'
    
    if not args.nhp:
        parcellation_info = select_parcellation_strategy(args.subject_folder, args.nhp)
        if parcellation_info['freesurfer_available']:
            fs_version = parcellation_info['freesurfer_version']
    
    reporting_cmd = f"""
# Generate standardized report
python3 /scripts/generate_standardized_report.py \\
    --subject {args.subject_name} \\
    --output_dir {output_path} \\
    --species {species_flag} \\
    --freesurfer_version {fs_version} \\
    --pipeline_type legacy_dti \\
    > {output_path}/reporting_log.txt 2>&1
"""
    commands.append(reporting_cmd)
    
    # Create bash shell script
    print("\n=== CREATING BATCH SCRIPT ===")
    batch_script = create_bash_script(commands, os.path.join(output_path, f"{args.subject_name}_dti_script.sh"))
    
    # Create SLURM batch file
    slurm_creator = SLURMFileCreator(args.subject_name, config)
    slurm_creator.create_bind_string(args.subject_folder)
    slurm_creator.create_batch_file(batch_script, args.nhp, skull_strip_cmd)
    
    print(f"\n=== LEGACY DTI PIPELINE PREPARATION COMPLETE ===")
    print(f"Subject: {args.subject_name}")
    print(f"Species: {'NHP' if args.nhp else 'Human'}")
    print(f"Pipeline: Legacy Single-Shell DTI")
    print(f"DTI Directory: {dti_dirname}")
    print(f"Shell Type: {shell_type}")
    print(f"B-values: {unique_bvals}")
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

def list_dti_directories(subject_folder):
    """
    Helper function to list all potential DTI directories for debugging.
    Can be called independently to check what DTI directories are found.
    """
    print(f"Searching for DTI directories in: {subject_folder}")
    
    patterns = [
        'DTI_S*', 'DTI*', 'DWI_S*', 'DWI*', 'DIFFUSION_S*', 'DIFFUSION*'
    ]
    
    found_dirs = []
    for pattern in patterns:
        dirs = glob.glob(os.path.join(subject_folder, pattern))
        dirs = [d for d in dirs if os.path.isdir(d)]
        found_dirs.extend(dirs)
    
    # Remove duplicates and sort
    found_dirs = sorted(list(set(found_dirs)))
    
    print(f"Found {len(found_dirs)} potential DTI directories:")
    for d in found_dirs:
        dir_name = os.path.basename(d)
        mrtrix_inputs = os.path.join(d, "mrtrix3_inputs")
        has_inputs = os.path.exists(mrtrix_inputs)
        print(f"  - {dir_name} {'(has mrtrix3_inputs)' if has_inputs else '(no mrtrix3_inputs)'}")
    
    return found_dirs

if __name__ == "__main__":
    main()