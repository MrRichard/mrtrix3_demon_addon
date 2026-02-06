# Use the existing mrtrix3 container as the base image.
# This assumes that the base image contains MRtrix3, FSL, ANTs, and other necessary neuroimaging tools.
FROM mrtrix3

# Install Python 3.10, pip, and curl, which are needed to install Poetry and the pipeline's dependencies.
# Use non-interactive mode and clean up apt cache to keep the image lean.
RUN apt-get update && 
    apt-get install -y --no-install-recommends 
    python3.10 
    python3-pip 
    curl 
 && rm -rf /var/lib/apt/lists/*

# Install Poetry, a modern Python dependency manager.
RUN curl -sSL https://install.python-poetry.org | python3.10 -

# Add Poetry's bin directory to the system's PATH.
# This allows running 'poetry' commands directly.
ENV PATH="/root/.local/bin:$PATH"

# Set the working directory inside the container to /app.
WORKDIR /app

# Copy the project's configuration file and the application source code.
# The source code is in the 'dwi_pipeline' directory.
COPY pyproject.toml ./
COPY dwi_pipeline/ ./dwi_pipeline/

# Install the project and its dependencies using Poetry.
# The --no-dev flag skips installation of development-only dependencies.
RUN poetry install --no-dev

# Set the container's entry point. When the container is run, it will execute
# the 'dwi-pipeline' command within the environment managed by Poetry.
ENTRYPOINT ["poetry", "run", "dwi-pipeline"]
