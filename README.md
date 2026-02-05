# MRtrix3 DWI Pipeline

A Python-based pipeline for processing diffusion-weighted imaging (DWI) data using MRtrix3 to generate structural connectivity matrices (connectomes).

## Overview

This pipeline processes BIDS-formatted DWI data through the following stages:

1. **Preprocessing**: Denoising, Gibbs ringing removal, distortion correction, bias field correction
2. **Response Function Estimation**: Automatic single-shell (Tournier) or multi-shell (dhollander) selection
3. **FOD Estimation**: Constrained Spherical Deconvolution (CSD or MSMT-CSD)
4. **Tractography**: Anatomically-constrained tractography with 10M streamlines
5. **SIFT Filtering**: Biologically plausible filtering to 1M streamlines
6. **Connectome Generation**: Structural connectivity matrices using multiple atlases

## BIDS Input Requirements

The pipeline expects BIDS-formatted input data:

```
bids_directory/
├── sub-01/
│   ├── anat/
│   │   └── sub-01_T1w.nii.gz
│   ├── dwi/
│   │   ├── sub-01_dir-AP_dwi.nii.gz
│   │   ├── sub-01_dir-AP_dwi.bvec
│   │   ├── sub-01_dir-AP_dwi.bval
│   │   ├── sub-01_dir-AP_dwi.json
│   │   ├── sub-01_dir-PA_dwi.nii.gz      # Optional: for rpe_pair correction
│   │   ├── sub-01_dir-PA_dwi.bvec
│   │   ├── sub-01_dir-PA_dwi.bval
│   │   └── sub-01_dir-PA_dwi.json
│   └── fmap/                              # Optional: for fieldmap correction
│       ├── sub-01_magnitude1.nii.gz
│       ├── sub-01_magnitude2.nii.gz
│       ├── sub-01_phasediff.nii.gz
│       └── sub-01_phasediff.json
└── derivatives/
    └── freesurfer/                        # Optional: for FreeSurfer atlases
        └── sub-01/
            └── mri/
                ├── aparc+aseg.mgz
                ├── aparc.a2009s+aseg.mgz
                └── brain.mgz
```

### Required Files
- T1w anatomical image (`*_T1w.nii.gz`)
- DWI image with at least one phase-encoding direction (`*_dir-AP_dwi.nii.gz` or `*_dwi.nii.gz`)
- Associated bvec and bval files

### Optional Files
- Reverse phase-encode DWI (`*_dir-PA_dwi.nii.gz`) for optimal distortion correction
- Fieldmap images for alternative distortion correction
- FreeSurfer derivatives for additional atlas-based connectomes

## Template Files

The `templates/` directory should contain MNI template and atlas files. Required files (configured in `config.json`):

- `mni_icbm152_nlin_sym_09a/mni_icbm152_t2_relx_tal_nlin_sym_09a.nii` - MNI T2 template
- `mni_icbm152_nlin_sym_09a/Brainnetome.nii.gz` - Brainnetome atlas

These files must be placed at the path specified in `config.json` under the `templates` key.

## Installation

### Dependencies

The pipeline requires the following software (typically run via Singularity containers):

- **MRtrix3** (with ANTs) - `mrtrix3_with_ants.sif`
- **FreeSurfer 7.4+** - `freesurfer_7.4.1.sif` (optional, for FreeSurfer atlases)
- **DeepBET** - `deepbet.sif` (optional, for NHP processing)

### Python Dependencies

```bash
pip install -e .
```

Or with the parent connectivity_shared package:

```bash
pip install -e ../connectivity_shared
pip install -e .
```

## Usage

### Basic Usage

```bash
# Human subject with default settings
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 --human

# With session
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 --session ses-01 --human

# Non-human primate
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 --nhp
```

### Advanced Options

```bash
# Custom output directory
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 \
    --output-dir /path/to/derivatives/mrtrix3/sub-01

# With external brain mask (skips dwi2mask step)
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 \
    --mask /path/to/brain_mask.nii.gz

# Force rerun all steps
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 --rerun

# Dry run (generate scripts without SLURM submission)
python run_pipeline.py --bids-dir /path/to/bids --subject sub-01 --dry-run
```

### Command Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--bids-dir` | Yes | Path to BIDS root directory |
| `--subject` | Yes | Subject ID (e.g., sub-01) |
| `--session` | No | Session ID (e.g., ses-01) |
| `--config` | No | Path to config JSON (default: config.json) |
| `--command-file` | No | Path to command JSON (default: enhanced_commands_bids.json) |
| `--output-dir` | No | Output directory (default: derivatives/mrtrix3/sub-XX/) |
| `--mask` | No | External brain mask path |
| `--human` | No | Process as human data (default) |
| `--nhp` | No | Process as non-human primate data |
| `--rerun` | No | Force rerun all steps |
| `--dry-run` | No | Generate scripts without SLURM submission |

## Output Structure

Output follows BIDS derivatives convention:

```
{bids_dir}/derivatives/mrtrix3/sub-XX/[ses-YY/]dwi/
├── dwi_ap.mif                          # Converted DWI
├── dwi_den.mif                         # Denoised DWI
├── dwi_den_preproc.mif                 # Preprocessed DWI
├── dwi_den_preproc_unbiased.mif        # Bias-corrected DWI
├── mask.mif                            # Brain mask
├── wmfod_norm.mif                      # Normalized FOD
├── 5tt_coreg.mif                       # 5-tissue segmentation
├── tracks_10M.tck                      # Raw tractography (10M)
├── sift_1M.tck                         # SIFT-filtered tracks (1M)
├── dwi_Brainnetome.nii.gz              # Brainnetome atlas in DWI space
├── connectome_Brainnetome_counts.csv   # Brainnetome connectome (counts)
├── connectome_Brainnetome_scaled.csv   # Brainnetome connectome (scaled)
├── connectome_FreeSurfer_DK_counts.csv # FreeSurfer DK connectome (if available)
├── connectome_FreeSurfer_DK_scaled.csv
├── connectome_FreeSurfer_Destrieux_counts.csv
├── connectome_FreeSurfer_Destrieux_scaled.csv
├── standardized_connectome_report.json # Harmonized metrics
├── standardized_connectome_report.html # QC visualization report
├── sub-XX_pipeline.sh                  # Generated pipeline script
└── *_log.txt                           # Per-step log files
```

## Distortion Correction

The pipeline automatically detects the best distortion correction strategy:

1. **rpe_pair** (Recommended): Both dir-AP and dir-PA DWI acquisitions available
2. **fieldmap**: Single DWI direction with magnitude/phasediff fieldmap images
3. **none**: No reverse PE or fieldmaps available (not recommended)

## Shell Configuration

The pipeline automatically detects shell configuration from bval files:

- **multi_shell**: 2+ distinct non-zero b-values → uses dhollander response, MSMT-CSD
- **single_shell**: 1 non-zero b-value → uses Tournier response, CSD, applies mrdegibbs

## Configuration

### config.json

```json
{
    "account": "your-slurm-account",
    "partition": "defq",
    "time": "8:00:00",
    "nodes": "1",
    "cpus": "8",
    "mem": "16G",
    "mrtrix3_sif": "container/mrtrix3_with_ants.sif",
    "fs7_sif": "container/freesurfer_7.4.1.sif",
    "deepbet_sif": "container/deepbet.sif",
    "templates": "/path/to/templates/"
}
```

## Group Analysis

Group analysis scripts are available in `scripts/`:

- `connectome_aggregator.py` - Aggregate standardized reports across subjects

These scripts may be migrated to `connectivity_shared` in future versions for cross-modal integration with the fMRI pipeline.

## Integration with connectivity_shared

This pipeline integrates with the `connectivity_shared` package for:

- Graph metrics computation (`connectivity_shared.graph_metrics`)
- Atlas label definitions (`connectivity_shared.atlas_labels`)
- QC visualization (`connectivity_shared.qc_visualization`)
- HTML report generation (`connectivity_shared.html_report`)

See the parent project's CLAUDE.md for details on the shared package.

## Troubleshooting

### Common Issues

1. **Missing bvec/bval files**: Ensure BIDS sidecar files are present alongside DWI images
2. **FreeSurfer atlases not found**: Check that FreeSurfer derivatives exist in `derivatives/freesurfer/`
3. **Template registration fails**: Verify template files exist at the configured path
4. **SLURM job fails**: Check individual step log files in the output directory

### Validation

Run the pipeline with `--dry-run` first to validate file discovery and step filtering without executing commands.
