import os

class SLURMFileCreator:
    
    def __init__(self, subjectname, config):
        self.config = config
        self.bind_string = ''
        self.subjectname = subjectname
        self.templatedir = os.path.abspath(self.config['templates'])
        # Get the directory where the script is running from
        self.scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    
    def create_bind_string(self, input_directory):
        input_directory = os.path.abspath(input_directory)
        # Add scripts directory binding
        self.bind_string = f"-B {input_directory}/:{input_directory} -B {self.templatedir}:/templates/ -B {self.scripts_dir}:/scripts"

    def create_batch_file(self, shell_script, is_nhp, skull_strip=''):
        # Create jobs directory if it doesn't exist
        os.makedirs('jobs', exist_ok=True)
        
        job_name = f"TRX_{self.subjectname[:8]}"
        with open(f'jobs/{self.subjectname}.slurm', 'w') as f:
            f.write("#!/bin/tcsh\n")
            f.write(f"#SBATCH --account={self.config['account']}\n")
            f.write(f"#SBATCH --partition={self.config['partition']}\n")
            f.write(f"#SBATCH --time={self.config['time']}\n")
            f.write(f"#SBATCH --nodes={self.config['nodes']}\n")
            f.write(f"#SBATCH --cpus-per-task={self.config['cpus']}\n")
            f.write(f"#SBATCH --job-name={job_name}\n")
            f.write(f"#SBATCH --mem={self.config['mem']}\n")
            f.write("module load singularity\n")
            if is_nhp:
                f.write(f"singularity exec --nv {self.bind_string} {self.config['deepbet_sif']} {skull_strip} \n")
            f.write(f"singularity exec --nv {self.bind_string} {self.config['mrtrix3_sif']} {shell_script}")