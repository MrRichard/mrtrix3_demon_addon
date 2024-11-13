#!/bin/bash
#SBATCH --job-name=MakeQC
#SBATCH --output=output.log
#SBATCH --error=error.log
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --partition=defq

# Set up Xvfb display
export DISPLAY=:99
/usr/bin/Xvfb :99 -screen 0 1024x768x24 &
XVFB_PID=$!

# Define the path to your Singularity image and script
SINGULARITY_IMAGE="container/mrtrix3_with_ants.sif"
SCRIPT_PATH="/isilon/datalake/riipl/original/DEMONco/mrtrix3_demon_addon/create_qc_images.sh"

# Run the script inside the Singularity container
echo "Running QC script in container"
singularity exec $SINGULARITY_IMAGE bash -c "$SCRIPT_PATH"

# Clean up Xvfb
kill $XVFB_PID

echo "Job completed."