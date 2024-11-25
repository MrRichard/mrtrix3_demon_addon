import argparse
from SlurmBatch import SLURMFileCreator
from ImageTypeChecker import ImageTypeChecker
import glob
import json
import os

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
        for command in commands:
            f.write(command)
            f.write("\n")
            
    return output_file

def load_global_config(file_path):
    global config
    with open(file_path, 'r') as f:
        config = json.load(f)

def main():
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

    print(f"Specie Selected: {'Non-Human Primate' if args.nhp else 'Human'}")
    
    # Check if DTI directory exists
    dti_directory = os.path.join(args.subject_folder, "DTI")
    if not os.path.exists(dti_directory):
        print("DTI directory is not present")
        exit(1)
        
    # Create output directories   
    output_path = os.path.join(args.subject_folder, "DTI", "mrtrix3_outputs")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load config options into global var space        
    load_global_config(args.config_file)
    
    # Build the mrtrix3 input files
    checker = ImageTypeChecker(args.subject_folder, args.config_file)

    # Build the skull-stripping command
    input_t1=find_t1_image(args.subject_folder)
    skull_strip_cmd = create_skullstrip_command(input_t1[0], args.nhp)
        
    # Load commands and convert to a list
    commands = load_commands(args.command_file, args.subject_folder, output_path, args.nhp, args.rerun)
    
    # create a bash shell
    batch_script = create_bash_script(commands, os.path.join(output_path, f"{args.subject_name}_script.sh"))
    slurm_creator = SLURMFileCreator(args.subject_name, config)
    slurm_creator.create_bind_string(args.subject_folder)
    slurm_creator.create_batch_file(batch_script, args.nhp, skull_strip_cmd)

if __name__ == "__main__":
    main()