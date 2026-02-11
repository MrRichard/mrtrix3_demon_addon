FROM mrtrix3/mrtrix3:latest

# Build Python 3.12 from source (bookworm only ships 3.11)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libssl-dev zlib1g-dev libbz2-dev \
        libreadline-dev libsqlite3-dev libncursesw5-dev \
        libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
        wget ca-certificates \
    && wget https://www.python.org/ftp/python/3.12.8/Python-3.12.8.tgz \
    && tar xzf Python-3.12.8.tgz \
    && cd Python-3.12.8 \
    && ./configure --enable-optimizations --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make altinstall \
    && cd / && rm -rf /Python-3.12.8 /Python-3.12.8.tgz \
    && rm -rf /var/lib/apt/lists/*

# Make Python 3.12 the default python3 so MRtrix3 scripts use it
# (the base image's minimal Python may be missing codecs like cp437)
RUN ln -sf /usr/local/bin/python3.12 /usr/local/bin/python3 \
    && python3.12 -m pip install --upgrade pip

ENV FSLDIR=/opt/fsl
ENV PATH="${FSLDIR}/bin:${PATH}"
ENV FSLOUTPUTTYPE=NIFTI_GZ

WORKDIR /app
COPY * /app
COPY dwi_pipeline/ ./dwi_pipeline/
RUN python3.12 -m pip install --no-cache-dir .
ENTRYPOINT ["python3.12", "-m", "dwi_pipeline"]