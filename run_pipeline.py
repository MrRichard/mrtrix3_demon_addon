import argparse
from SlurmBatch import SLURMFileCreator
import glob
import json
import os

def load_commands(file_path, input_path, output_path, rerun=False):
    
    # load json commands file
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # find T1 anat file
    pattern = os.path.join(os.path.join(input_path,'DTI'), '3*-tfl3d116ns.nii')
    matching_files = glob.glob(pattern)
    
    # build command list    
    commands = []
    
    for step in data['steps']:
        print(f"- writing step: {step['name']}")
        validation_output = step['validation_output'].replace("OUTPUT", output_path)
        command = step['cmd'].replace("INPUT", input_path).replace("OUTPUT", output_path).replace("ANAT", matching_files[0]).replace("TEMPLATE", 'templates')
        log_file = os.path.join(output_path, f"{step['name']}_log.txt")
        command_with_logging = f"{command} > {log_file} 2>&1"
        if rerun:
            commands.append(command_with_logging)
        else:
            commands.append(f'if [ ! -f {validation_output} ]; then\n  {command_with_logging}\nfi')
    return commands

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
    
    args = parser.parse_args()
    
    # Create working and output directories   
    output_path = os.path.join(args.output, args.subject_name)
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load config options into global var space        
    load_global_config(args.config_file)
        
    # Load commands and convert to a list
    commands = load_commands(args.command_file, args.subject_folder, output_path, args.rerun)
    
    # create a bash shell
    batch_script = create_bash_script(commands, os.path.join(output_path, f"{args.subject_name}_script.sh"))
    slurm_creator = SLURMFileCreator(args.subject_name, config)
    slurm_creator.create_bind_string(args.subject_folder, output_path)
    slurm_creator.create_batch_file(batch_script)

if __name__ == "__main__":
    main()