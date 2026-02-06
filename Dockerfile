# Use the official MRtrix3 container as the base image.
# This provides MRtrix3 and core neuroimaging tools.
FROM mrtrix3/mrtrix3:latest

# Install Python 3 and pip.
# Use non-interactive mode and clean up apt cache to keep the image lean.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container to /app.
WORKDIR /app

# Copy the requirements file and install dependencies.
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the application source code.
COPY dwi_pipeline/ ./dwi_pipeline/

# Set the container's entry point to run the pipeline module.
ENTRYPOINT ["python3", "-m", "dwi_pipeline"]
