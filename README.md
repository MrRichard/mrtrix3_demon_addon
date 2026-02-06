# DWI Pipeline (MRtrix3 Module)

A containerized DWI processing pipeline that uses [Nipype](https://nipype.readthedocs.io/) to orchestrate MRtrix3, FSL, and ANTs commands. Processes BIDS-formatted diffusion-weighted imaging data into structural connectivity matrices.

Part of the [combined_connectivity](../) project for harmonized brain connectivity analysis.

## Prerequisites

- **BIDS-formatted dataset** with DWI and T1w data (with JSON sidecars)
- **FreeSurfer recon-all output** — this is **mandatory**; the pipeline will fail without it
- Docker or Singularity for containerized execution

### Required Input Structure

```
/path/to/bids/
  sub-01/
    ses-01/                              # Session directory (optional)
      dwi/
        sub-01_ses-01_dir-AP_dwi.nii.gz  # Primary DWI (required)
        sub-01_ses-01_dir-AP_dwi.bval    # b-values (required)
        sub-01_ses-01_dir-AP_dwi.bvec    # b-vectors (required)
        sub-01_ses-01_dir-AP_dwi.json    # JSON sidecar (required)
        sub-01_ses-01_dir-PA_dwi.nii.gz  # Reverse PE DWI (optional, enables topup)
      anat/
        sub-01_ses-01_T1w.nii.gz         # T1-weighted image (required)
        sub-01_ses-01_T1w.json           # T1w JSON sidecar (required)
      fmap/                              # Fieldmaps (optional, alternative distortion correction)
        sub-01_ses-01_phasediff.nii.gz
        sub-01_ses-01_magnitude1.nii.gz
        sub-01_ses-01_magnitude2.nii.gz

/path/to/freesurfer/
  sub-01/
    mri/
      aparc+aseg.mgz                     # Desikan-Killiany parcellation (required)
      brain.mgz                          # Brain-extracted T1 (required)
      aparc.a2009s+aseg.mgz              # Destrieux parcellation (optional)
```

### Required JSON Sidecar Fields

The DWI JSON sidecar must contain either:
- `PhaseEncodingDirection` and `TotalReadoutTime`, **or**
- `PhaseEncodingDirection`, `EffectiveEchoSpacing`, and `ReconMatrixPE` (readout time will be calculated)

For fieldmap-based distortion correction, the phasediff JSON must contain `EchoTime1` and `EchoTime2`.

## Building the Container

### Docker

```bash
docker build -t dwi-pipeline .
```

### Singularity

```bash
singularity build dwi-pipeline.sif Singularity.def
```

Both containers use the official `mrtrix3/mrtrix3:latest` as the base image and install Python 3 + dependencies on top.

## Usage

### Docker

```bash
docker run --rm \
  -v /path/to/bids:/data:ro \
  -v /path/to/freesurfer:/freesurfer:ro \
  -v /path/to/output:/out \
  dwi-pipeline:latest \
  01 01
```

### Singularity

```bash
singularity run \
  -B /path/to/bids:/data:ro \
  -B /path/to/freesurfer:/freesurfer:ro \
  -B /path/to/output:/out \
  dwi-pipeline.sif \
  01 01
```

### CLI Arguments

```
positional arguments:
  subject               Subject ID (e.g., 01)
  session               Session ID (e.g., 01)

Processing Options:
  --n-threads N         Number of threads (default: 4)
  --species {human,nhp} Species (default: human)
  --rerun               Force rerun all steps (ignore Nipype cache)

Directory Options:
  --bids-dir PATH       BIDS dataset directory (default: /data)
  --freesurfer-dir PATH FreeSurfer derivatives directory (default: /freesurfer)
  --output-dir PATH     Output directory (default: /out)
  --work-dir PATH       Working directory for intermediates (default: /tmp/work)

Advanced Options:
  --verbose, -v         Increase verbosity (-v for INFO, -vv for DEBUG)
```

### SLURM Batch Example

```bash
#!/bin/bash
#SBATCH --job-name=dwi-pipeline
#SBATCH --array=1-10
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G

SUBJECTS=(sub-01 sub-02 sub-03 sub-04 sub-05 sub-06 sub-07 sub-08 sub-09 sub-10)
SUBJECT=${SUBJECTS[$SLURM_ARRAY_TASK_ID-1]}

singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/derivatives/dwi:/out \
  dwi-pipeline.sif \
  ${SUBJECT#sub-} 01 --n-threads 8
```

## Automatic Detection

The pipeline automatically detects processing parameters from your data:

**Shell configuration** — determined from the b-value file:
- **Single-shell** (1 unique non-zero b-value): Uses `dwi2response tournier` + `dwi2fod csd`, applies Gibbs ringing removal, FOD cutoff 0.1
- **Multi-shell** (2+ unique non-zero b-values): Uses `dwi2response dhollander` + `dwi2fod msmt_csd`, skips degibbs, FOD cutoff 0.06

**Distortion correction** — determined from available files (priority order):
1. **RPE pair**: Both dir-AP and dir-PA DWI exist → topup + eddy
2. **Fieldmap**: Phasediff + magnitude images exist → fieldmap-based correction
3. **None**: Only eddy current correction

## Pipeline Steps

1. **mrconvert** — NIfTI to MIF with gradient embedding
2. **dwidenoise** — Marchenko-Pastur PCA denoising
3. **mrdegibbs** — Gibbs ringing removal (single-shell only)
4. **dwifslpreproc** — Distortion correction via topup/eddy
5. **dwibiascorrect** — ANTs-based bias field correction
6. **dwi2mask** — Brain mask generation
7. **dwi2response** — Response function estimation (tournier or dhollander)
8. **dwi2fod** — Fiber orientation distribution estimation (CSD or MSMT-CSD)
9. **5ttgen** — 5-tissue-type segmentation from registered T1w
10. **tckgen** — Whole-brain tractography (iFOD2, 10M streamlines)
11. **tcksift2** — SIFT2 streamline filtering (1M output)
12. **tck2connectome** — Structural connectivity matrix generation

## Development

### Local Setup (without container)

```bash
pip install -r requirements.txt
```

### Running Tests

```bash
pytest tests/
pytest tests/unit/domain/test_models.py -v   # Single file
```

### Running Outside Container

```bash
python -m dwi_pipeline 01 01 \
  --bids-dir /path/to/bids \
  --freesurfer-dir /path/to/freesurfer \
  --output-dir /path/to/output \
  --work-dir /tmp/work \
  -vv
```

Requires MRtrix3, FSL, and ANTs to be installed and on your PATH.

## Dependencies

- **Python**: 3.10+
- **Nipype**: 1.8.6+
- **NumPy**: 1.26+
- **Container tools**: MRtrix3, FSL (BET, FLIRT), ANTs
