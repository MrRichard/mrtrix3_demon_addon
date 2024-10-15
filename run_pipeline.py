import argparse
from SlurmBatch import SLURMFileCreator
from ImageTypeChecker import ImageTypeChecker
import glob
import json
import os

def find_t1_image(input_path):
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'DTI'), '*-tfl3d116*.nii')
    matching_files = glob.glob(pattern)
    return matching_files


def load_commands(file_path, input_path, output_path, is_nhp=False, rerun=False):
    
    # load json commands file
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    matching_files = find_t1_image(input_path)

    matching_mask_file=''
    if is_nhp:
        matching_mask_file = matching_files[0].replace('.nii', '_pre_mask.nii.gz')
        print(f'Preselecting mask file: {matching_mask_file}')

    # build command list    
    commands = []
    
    for step in data['steps']:
        print(f"- writing step: {step['name']}")
        validation_output = step['validation_output'].replace("OUTPUT", output_path)
        
        command = step['cmd'].replace("INPUT", input_path).replace("OUTPUT", output_path).replace("ANAT", matching_files[0]).replace("TEMPLATE", '/templates').replace("MASK", matching_mask_file)
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