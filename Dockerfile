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

# Keep Python 3.12 isolated — do NOT override python3, which MRtrix3
# scripts depend on (the base image's Python 3.8 has codecs like cp437
# that the from-source build may lack). Use python3.12 explicitly.
RUN python3.12 -m pip install --upgrade pip

# Patch MRtrix3's Python lib: replace cp437 codec (file-based, often
# missing in minimal/from-source Pythons) with latin-1 (built-in,
# always available). Both are single-byte → functionally identical
# for parsing mrstats ASCII output.
RUN grep -rl "cp437" /opt/mrtrix3/lib/ | xargs sed -i "s/'cp437'/'latin-1'/g" || true

ENV FSLDIR=/opt/fsl
ENV PATH="${FSLDIR}/bin:${PATH}"
ENV FSLOUTPUTTYPE=NIFTI_GZ

WORKDIR /app
COPY * /app
COPY dwi_pipeline/ ./dwi_pipeline/
RUN python3.12 -m pip install --no-cache-dir .
ENTRYPOINT ["python3.12", "-m", "dwi_pipeline"]