class SLURMFileCreator:
    
    def __init__(self, subjectname, config):
        self.config = config
        self.bind_string = ''
        self.subjectname = subjectname
        
    def create_bind_string(self, input_directory, output_directory):
        self.bind_string = f"-B {input_directory}/:/input/ -B {output_directory}/:/output/"

    def create_batch_file(self, shell_script):
        with open(f'{self.subjectname}.slurm', 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"#SBATCH --account={self.config['account']}\n")
            f.write(f"#SBATCH --partition={self.config['partition']}\n")
            f.write(f"#SBATCH --time={self.config['time']}\n")
            f.write(f"#SBATCH --nodes={self.config['nodes']}\n")
            f.write(f"#SBATCH --cpus-per-task={self.config['cpus']}\n")
            f.write("\nmodule load singularity\n")
            f.write(f"singularity exec --nv {self.bind_string} {self.config['sif']} {shell_script}")