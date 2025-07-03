import argparse
from SlurmBatch import SLURMFileCreator
from ImageTypeChecker import ImageTypeChecker
import glob
import json
import os
import logging

def find_t1_image(input_path):
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-tfl3d116*.info')
    matching_files = glob.glob(pattern)
    
    # Replace the suffix ".info" with ".nii" for each matching file
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_t1_brainmask_image(input_path):
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'nifti','cat12'), '*tfl3d116ns_bet_mask.nii.gz')
    matching_files = glob.glob(pattern)
    
    # Replace the suffix ".info" with ".nii" for each matching file
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_t2_image(input_path):
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-spc2*.info')
    matching_files = glob.glob(pattern)
    
    # Replace the suffix ".info" with ".nii" for each matching file
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_flair_image(input_path):
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'nifti'), '*-spcir*.info')
    matching_files = glob.glob(pattern)
    
    # Replace the suffix ".info" with ".nii" for each matching file
    matching_files = [f.replace('.info', '.nii') for f in matching_files]
    
    return matching_files

def find_largest_and_smallest_MOSAIC(input_path):
    # find the largest and smallest MOSAIC files in the mrtrix3_inputs directory
    folder_path = os.path.join(input_path, "mrtrix3_inputs")

    # list of all .nii files in the folder, ignoring those with 'PHASE' or 'SBREF'
    nii_files = [f for f in os.listdir(folder_path) if f.endswith('.nii.gz') and 'PHASE' not in f and 'SBREF' not in f]

    # check if there are any .nii.gz files
    if nii_files:
        # get sizes of the files
        file_sizes = {f: os.path.getsize(os.path.join(folder_path, f)) for f in nii_files}

        # get the max and min file sizes 
        max_size = max(file_sizes.values())
        min_size = min(file_sizes.values())

        # get all files with the max and min sizes
        max_size_files = [f for f, size in file_sizes.items() if size == max_size]
        min_size_files = [f for f, size in file_sizes.items() if size == min_size]

        # if more than one file for max size, check if "A2P_MOSAIC.nii" is in the list and return it
        if len(max_size_files) > 1 and "A2P_MOSAIC.nii.gz" in max_size_files:
            largest_image = "A2P_MOSAIC.nii.gz"
        else:
            largest_image = max_size_files[0]
        
        # if more than one file for min size, check if "P2A_MOSAIC.nii" is in the list and return it
        if len(min_size_files) > 1 and "P2A_MOSAIC.nii.gz" in min_size_files:
            smallest_image = "P2A_MOSAIC.nii.gz"
        else:
            smallest_image = min_size_files[0]

        return os.path.join(folder_path,largest_image), os.path.join(folder_path,smallest_image)
    
    # if no .nii files in the directory
    else:
        print("No .nii.gz files found in the mrtrix3_inputs directory")
        return None, None
    
def parse_dir_codes(largest_file, smallest_file):
    # Extract the prefixes by splitting the filenames
    largest_basename = os.path.basename(largest_file)
    smallest_basename = os.path.basename(smallest_file)
    
    # Determine the prefix and lower case code for the largest file
    if largest_basename.startswith("A2P"):
        larger_prefix = "A2P"
        lower_case_code = "ap"
    elif largest_basename.startswith("P2A"):
        larger_prefix = "P2A"
        lower_case_code = "pa"
    else:
        raise ValueError("Largest filename does not have a recognized prefix: expected 'A2P' or 'P2A'")

    # Determine the prefix for the smallest file
    if smallest_basename.startswith("A2P"):
        smaller_prefix = "A2P"
    elif smallest_basename.startswith("P2A"):
        smaller_prefix = "P2A"
    else:
        raise ValueError("Smallest filename does not have a recognized prefix: expected 'A2P' or 'P2A'")
    return larger_prefix, smaller_prefix, lower_case_code
    
def read_mosaic_json(input_file):
    # Check if the input file has the expected format and create the corresponding JSON file path
    if not input_file.endswith('_MOSAIC.nii.gz'):
        raise ValueError("Input file must be a path to a *_MOSAIC.nii.gz file")

    # Construct the path for the associated JSON file
    json_file_path = input_file.replace('.nii.gz', '.json')

    # Check if the JSON file exists
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"No associated JSON file found at {json_file_path}")
    # Read the associated JSON file and return the content as a dictionary
    with open(json_file_path, 'r') as json_file:
        json_data = json.load(json_file)
    return json_data


def load_commands(file_path, input_path, output_path, is_nhp=False, rerun=False):
    
    # load json commands file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Identify the largest MOSAIC file
    large_mosaic, small_mosaic = find_largest_and_smallest_MOSAIC(input_path)
    mosaic_json = read_mosaic_json(large_mosaic)
    larger_prefix, smaller_prefix, lower_case_code = parse_dir_codes(large_mosaic, small_mosaic)
    readouttime = mosaic_json['TotalReadoutTime']
    repetitiontime = mosaic_json['RepetitionTime']
    
    # Identify T1w input image
    matching_t1w_files = find_t1_image(input_path)

    # Identify T2 FLAIR image
    matching_flair_files = find_flair_image(input_path)

    # Identify NHP brain masks
    matching_mask_file=''
    if is_nhp:
        matching_mask_file = matching_t1w_files[0].replace('.nii', '_pre_mask.nii.gz')
        print(f'Preselecting mask file: {matching_mask_file}')
    else:
        matching_brainmask_images = find_t1_brainmask_image(input_path)
        matching_mask_file = matching_brainmask_images[0]
        print(f'Preselecting mask file: {matching_mask_file}')

    print(f"T1w Image file: ${matching_t1w_files[0]}")
    print(f"T2w Image file: ${matching_flair_files[0]}")

    # build command list    
    commands = []

    # Define all text replacements
    replacements = {
        "INPUT": input_path,
        "OUTPUT": output_path,
        "ANAT": matching_t1w_files[0],
        "FLAIR" : matching_flair_files[0],
        "TEMPLATE": '/templates',
        "MASK": matching_mask_file,
        "PIXDIM4" : str(repetitiontime),
        "READOUTTIME" : str(readouttime),
        "PRIMARY" : larger_prefix,
        "SECONDARY" : smaller_prefix,
        "PE_DIR" : lower_case_code
    }

    
    for step in data['steps']:
        print(f"- writing step: {step['name']}")
        validation_output = step['validation_output']
        for placeholder, value in replacements.items():
            validation_output = validation_output.replace(placeholder, value)
        
        # create command scripts
        command = step['cmd']
        for placeholder, value in replacements.items():
            command = command.replace(placeholder, value)

        # define output logs
        log_file = os.path.join(output_path, f"{step['name']}_log.txt")
        command_with_logging = f"{command} > {log_file} 2>&1"

        if rerun:
            commands.append(command_with_logging)
        else:
            commands.append(f'if [ ! -f {validation_output} ]; then\n  {command_with_logging}\nfi')
    return commands

def create_skullstrip_command(input_image, is_nhp):
    if is_nhp:
        # Construct the command for non-human primates using deepbet's muSkullStrip
        # Assuming `selected_model.model` and output directory locations are defined elsewhere
        model_path = "/UNet_Model/models/Site-All-T-epoch_36.model"
        output_dir = os.path.dirname(input_image)
        command = f"python3 /UNet_Model/muSkullStrip.py -in {input_image} -model {model_path} -out {output_dir}"
    else: 
        print("Human image processing uses dwi2mask fsl in pipeline")
        return False
    
    # Return the constructed command
    return command
    
def create_bash_script(commands, output_file):
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

def load_global_config(file_path):
    global config
    with open(file_path, 'r') as f:
        config = json.load(f)

def detect_freesurfer_version(subject_folder):
    """
    Detect available FreeSurfer versions and return the best one with warnings.
    Priority: freesurfer8.0 > FreeSurfer7 > FreeSurfer (5.3)
    """
    fs_dirs = {
        'freesurfer8.0': 'freesurfer8.0', # Version 8.0.0
        'FreeSurfer7': 'FreeSurfer7', # Version 7.2
        'FreeSurfer': 'FreeSurfer'  # Version 5.3
    }
    
    available_versions = {}
    
    for version, dirname in fs_dirs.items():
        if dirname == 'freesurfer8.0':
            fs_path = os.path.join(subject_folder, dirname, os.path.basename(subject_folder))
        else:
            fs_path = os.path.join(subject_folder, dirname)

        if os.path.exists(fs_path):
            # Check for key FreeSurfer files
            aparc_aseg = os.path.join(fs_path, 'mri', 'aparc+aseg.mgz')
            if os.path.exists(aparc_aseg):
                available_versions[version] = fs_path
    
    if not available_versions:
        return None, None, "No valid FreeSurfer reconstruction found"
    
    # Select best version with appropriate warnings
    if 'freesurfer8.0' in available_versions:
        return 'freesurfer8.0', available_versions['freesurfer8.0'], None
    elif 'FreeSurfer7' in available_versions:
        warning = "Using FreeSurfer 7 - consider upgrading to FreeSurfer 8.0 for optimal results"
        return 'FreeSurfer7', available_versions['FreeSurfer7'], warning
    else:
        warning = "WARNING: Using FreeSurfer 5.3 - strongly recommend upgrading to FreeSurfer 7+ for better results"
        return 'FreeSurfer', available_versions['FreeSurfer'], warning

def find_freesurfer_files(fs_path, is_nhp=False):
    """
    Find required FreeSurfer files for connectome generation.
    Returns paths to aparc+aseg.mgz and other needed files.
    """
    if is_nhp:
        return None  # NHPs don't use FreeSurfer
    
    files = {
        'aparc_aseg': os.path.join(fs_path, 'mri', 'aparc+aseg.mgz'),
        'aparc_dk': os.path.join(fs_path, 'mri', 'aparc.DKTatlas+aseg.mgz'),
        'aparc_destrieux': os.path.join(fs_path, 'mri', 'aparc.a2009s+aseg.mgz'),
        'orig': os.path.join(fs_path, 'mri', 'orig.mgz'),
        'brain': os.path.join(fs_path, 'mri', 'brain.mgz')
    }
    
    # Check which files exist
    available_files = {}
    for key, path in files.items():
        if os.path.exists(path):
            available_files[key] = path
    
    return available_files

def select_parcellation_strategy(subject_folder, is_nhp=False):
    """
    Determine the best parcellation strategy based on available data.
    Returns strategy info for both humans and NHPs.
    """
    if is_nhp:
        return {
            'strategy': 'template_only',
            'atlases': ['Brainnetome'],
            'freesurfer_available': False,
            'warning': None
        }
    
    # For humans, check FreeSurfer availability
    fs_version, fs_path, fs_warning = detect_freesurfer_version(subject_folder)
    
    if fs_version:
        fs_files = find_freesurfer_files(fs_path)
        
        # Determine available atlases
        available_atlases = ['Brainnetome']  # Always available via template
        
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

def create_enhanced_replacements(input_path, output_path, is_nhp=False):
    """
    Enhanced replacement dictionary that includes FreeSurfer paths when available.
    """
    # Get basic replacements (your existing logic)
    large_mosaic, small_mosaic = find_largest_and_smallest_MOSAIC(input_path)
    mosaic_json = read_mosaic_json(large_mosaic)
    larger_prefix, smaller_prefix, lower_case_code = parse_dir_codes(large_mosaic, small_mosaic)
    readouttime = mosaic_json['TotalReadoutTime']
    repetitiontime = mosaic_json['RepetitionTime']
    
    matching_t1w_files = find_t1_image(input_path)
    matching_flair_files = find_flair_image(input_path)
    
    # Handle masks
    if is_nhp:
        matching_mask_file = matching_t1w_files[0].replace('.nii', '_pre_mask.nii.gz')
    else:
        matching_brainmask_images = find_t1_brainmask_image(input_path)
        matching_mask_file = matching_brainmask_images[0]

    # Base replacements
    replacements = {
        "INPUT": input_path,
        "OUTPUT": output_path,
        "ANAT": matching_t1w_files[0],
        "FLAIR": matching_flair_files[0],
        "TEMPLATE": '/templates',
        "MASK": matching_mask_file,
        "PIXDIM4": str(repetitiontime),
        "READOUTTIME": str(readouttime),
        "PRIMARY": larger_prefix,
        "SECONDARY": smaller_prefix,
        "PE_DIR": lower_case_code
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
            # Provide empty values if FreeSurfer not available
            replacements.update({
                "FREESURFER_DIR": "",
                "FS_APARC_ASEG": "",
                "FS_APARC_DK": "",
                "FS_APARC_DESTRIEUX": "",
                "FS_BRAIN": "",
                "FS_VERSION": "none"
            })
    
    return replacements, parcellation_info if not is_nhp else None

def load_commands_enhanced(file_path, input_path, output_path, is_nhp=False, rerun=False):
    """
    Enhanced version of load_commands that handles FreeSurfer integration and species-specific processing.
    """
    # Load JSON commands file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Get enhanced replacements including FreeSurfer paths
    replacements, parcellation_info = create_enhanced_replacements(input_path, output_path, is_nhp)
    
    # Add subject name placeholder (will be filled in main)
    replacements['SUBJECT_NAME'] = 'PLACEHOLDER_SUBJECT'
    replacements['SPECIES'] = 'nhp' if is_nhp else 'human'
    
    commands = []
    skipped_steps = []
    
    # Log FreeSurfer information for humans
    if not is_nhp and parcellation_info:
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")
        
        print(f"FreeSurfer Strategy: {parcellation_info['strategy']}")
        print(f"Available Atlases: {', '.join(parcellation_info['atlases'])}")
        
        if parcellation_info['freesurfer_available']:
            print(f"FreeSurfer Version: {parcellation_info['freesurfer_version']}")
            print(f"FreeSurfer Path: {parcellation_info['freesurfer_path']}")

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
    
    # Log skipped steps
    if skipped_steps:
        print(f"\nSkipped Steps:")
        for skipped in skipped_steps:
            print(f"  - {skipped}")
    
    return commands

def main_enhanced():
    """Enhanced main function with FreeSurfer integration and improved logging."""
    parser = argparse.ArgumentParser(description='Generate SLURM batch files for given subject.')
    parser.add_argument('subject_name', type=str, help='Name of the subject')
    parser.add_argument('subject_folder', type=str, help='Path to the subject folder')
    parser.add_argument('config_file', type=str, help='Path to the config json file')
    parser.add_argument('command_file', type=str, help='Path to the command json file')
    parser.add_argument('-o','--output', type=str, 
                        help='Path to the output folder', 
                        default="output",
                        required=False)
    parser.add_argument('-r','--rerun', type=bool, 
                        help='Force rerun of all steps', 
                        default=False,
                        required=False)
    
    # Mutually exclusive group for species selection
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--nhp', dest='nhp', action='store_true', 
                       help='Use non-human primate model')
    group.add_argument('--human', dest='human', action='store_true', 
                       help='Use human model (default)')
    
    args = parser.parse_args()

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
    
    # Check if DTI directory exists
    dti_directory = os.path.join(args.subject_folder, "DTI")
    if not os.path.exists(dti_directory):
        print("ERROR: DTI directory is not present")
        exit(1)
        
    # Create output directories   
    output_path = os.path.join(args.subject_folder, "DTI", "mrtrix3_outputs")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load config options into global var space        
    load_global_config(args.config_file)
    
    # Ensure scripts directory exists and is accessible
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    if not os.path.exists(scripts_dir):
        print(f"ERROR: Scripts directory not found at {scripts_dir}")
        print("Creating scripts directory...")
        os.makedirs(scripts_dir, exist_ok=True)
    
    # Check if generate_standardized_report.py exists
    report_script = os.path.join(scripts_dir, 'generate_standardized_report.py')
    if not os.path.exists(report_script):
        print(f"WARNING: generate_standardized_report.py not found at {report_script}")
        print("The reporting step may fail. Please ensure the script is in the scripts/ directory.")
    
    # Build the mrtrix3 input files
    print("\n=== BUILDING MRTRIX3 INPUTS ===")
    checker = ImageTypeChecker(args.subject_folder, args.config_file)
    
    # For humans, analyze FreeSurfer availability
    if not args.nhp:
        print("\n=== FREESURFER ANALYSIS ===")
        parcellation_info = select_parcellation_strategy(args.subject_folder, args.nhp)
        if parcellation_info['warning']:
            print(f"WARNING: {parcellation_info['warning']}")

    # Build the skull-stripping command
    input_t1 = find_t1_image(args.subject_folder)
    skull_strip_cmd = create_skullstrip_command(input_t1[0], args.nhp)
        
    # Load commands and convert to a list
    print("\n=== BUILDING COMMAND LIST ===")
    commands = load_commands_enhanced(args.command_file, args.subject_folder, output_path, args.nhp, args.rerun)
    
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
    > {output_path}/reporting_log.txt 2>&1
"""
    commands.append(reporting_cmd)
    
    # Create a bash shell script
    print("\n=== CREATING BATCH SCRIPT ===")
    batch_script = create_bash_script(commands, os.path.join(output_path, f"{args.subject_name}_script.sh"))
    
    # Create SLURM batch file
    slurm_creator = SLURMFileCreator(args.subject_name, config)
    slurm_creator.create_bind_string(args.subject_folder)
    slurm_creator.create_batch_file(batch_script, args.nhp, skull_strip_cmd)
    
    print(f"\n=== PIPELINE PREPARATION COMPLETE ===")
    print(f"Subject: {args.subject_name}")
    print(f"Species: {'NHP' if args.nhp else 'Human'}")
    print(f"Output Directory: {output_path}")
    print(f"Total Commands: {len(commands)}")
    print(f"Scripts Directory: {scripts_dir}")
    
    if not args.nhp:
        print(f"FreeSurfer Version: {fs_version}")
    
    print(f"Batch Script: {batch_script}")
    print(f"Ready for SLURM submission!")

# You can also create a wrapper function to maintain backward compatibility
def main():
    """Wrapper to maintain backward compatibility."""
    main_enhanced()

if __name__ == "__main__":
    main()