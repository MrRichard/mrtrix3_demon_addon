#!/bin/bash

for x in ./jobs/*.slurm; do
    job_basename=$(basename "$x" .slurm)
    sbatch_file="${job_basename}_new.slurm"

    cat <<EOL > qc_jobs/$sbatch_file
#!/bin/bash
#!/bin/bash 
#SBATCH --job-name=mkQC_$job_basename 
#SBATCH --output=logs/${job_basename}.out 
#SBATCH --error=logs/${job_basename}.err 
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=10G

module load singularity
Xvfb :99 -ac -nolisten tcp -noreset -screen 0 1024x768x24 &
export DISPLAY=:99
singularity run -B /isilon/datalake/riipl/original/ADRC:/data/ ./container/mrtrix3_with_ants.sif bash ./create_qc_images.sh /data/${job_basename}

EOL

done
