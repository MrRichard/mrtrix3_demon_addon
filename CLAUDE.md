# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A containerized DWI (diffusion-weighted imaging) processing pipeline that uses Nipype to orchestrate MRtrix3/FSL/ANTs commands. It processes BIDS-formatted DWI data into structural connectivity matrices. Part of the larger `combined_connectivity` project (see `../CLAUDE.md`).

## Commands

### Running the Pipeline (inside container)
```bash
# Basic usage (positional: subject session)
python -m dwi_pipeline sub-01 ses-01

# With options
python -m dwi_pipeline sub-01 ses-01 --species human --n-threads 16 --rerun

# Custom directories (defaults assume container mounts: /data, /freesurfer, /out, /tmp/work)
python -m dwi_pipeline sub-01 ses-01 \
    --bids-dir /path/to/bids \
    --freesurfer-dir /path/to/freesurfer \
    --output-dir /path/to/output \
    --work-dir /path/to/work

# Verbosity: -v (INFO), -vv (DEBUG)
python -m dwi_pipeline sub-01 ses-01 -vv
```

### Building Containers
```bash
docker build -t dwi-pipeline .
singularity build dwi-pipeline.sif Singularity.def
```

### Running Tests
```bash
pytest tests/
pytest tests/unit/domain/test_enums.py      # Single test file
pytest tests/unit/domain/test_models.py -k "test_shell_detection"  # Single test
```

### Installing for Development
```bash
pip install -r requirements.txt
# Or with Poetry: poetry install
```

## Architecture

### Layered Architecture

Dependencies point inward only — domain has zero external dependencies.

```
CLI (cli/)                    → Argument parsing, config loading
Application (application/)    → Orchestration: factories, strategies, builders
Domain (domain/)              → Pure business logic: models, enums, validation, exceptions
Infrastructure (infrastructure/) → External tools: BIDS reader, Nipype interfaces, FreeSurfer
```

### Pipeline Execution Flow

```
__main__.py
  → BidsReader.discover()           # Find DWI/T1w/fieldmap files in BIDS dir
  → FreeSurferValidator.validate()  # Check aparc+aseg.mgz, brain.mgz exist
  → BidsMetadataExtractor           # Extract PE direction, readout time, shell config
  → WorkflowFactory                 # Select strategy, build Nipype workflow
    → StrategyFactory               # Pick SingleShell or MultiShell strategy
    → WorkflowBuilder               # Builder pattern: preprocessing → response → FOD → tractography
    → WorkflowDirector              # Template method: calls builder steps in order
  → workflow.run()                  # Nipype executes the DAG
```

### Strategy Pattern (Single vs Multi-Shell)

Shell type is auto-detected from b-values (values > 50 are non-zero, rounded to nearest 50):

| Aspect | Single-Shell | Multi-Shell |
|--------|-------------|-------------|
| Response | `dwi2response tournier` | `dwi2response dhollander` (3 outputs: WM/GM/CSF) |
| FOD | `dwi2fod csd` | `dwi2fod msmt_csd` (3 tissue ODFs) |
| Degibbs | Applied | Skipped |
| FOD cutoff | 0.1 | 0.06 |

Strategy selection is keyed on `(Species, ShellType)` in `StrategyFactory`.

### Distortion Correction (auto-detected)

- **RPE_PAIR**: Both dir-AP and dir-PA DWI exist → `dwifslpreproc -rpe_pair`
- **FIELDMAP**: Single DWI + phasediff/magnitude fmaps → fieldmap-based correction
- **NONE**: No reverse PE or fieldmaps → eddy only

### Nipype Workflow Stages

1. **Preprocessing**: mrconvert → dwidenoise → [mrdegibbs] → dwifslpreproc → dwibiascorrect → dwi2mask
2. **Response**: tournier (single) or dhollander (multi-shell, outputs 3 response files)
3. **FOD**: csd (single) or msmt_csd (multi-shell, outputs 3 tissue FODs)
4. **Tractography**: dwiextract b0 → BET T1w → FLIRT T1→DWI → 5ttgen → 5tt2gmwmi → tckgen (iFOD2, 10M) → tcksift2 (1M) → tck2connectome

### Key Domain Models

- **BidsLayout** (`domain/models/bids_layout.py`): Discovered BIDS file paths + derived shell/distortion config
- **DwiData** (`domain/models/dwi_data.py`): Extracted metadata with auto shell detection in `__post_init__`
- **ProcessingConfig** (`domain/models/processing_config.py`): User params + derived `run_id`, `nipype_work_dir`, `subject_output_dir`

### Nipype Interface Wrappers

Custom `CommandLine` subclasses in `infrastructure/interfaces/` wrap MRtrix3, FSL, and ANTs commands. Notable complexity:
- **DWI2FOD**: Overrides `cmdline` property for multi-shell positional arg ordering
- **DWI2Response dhollander**: Custom `_list_outputs()` for 3 output files (WM/GM/CSF)
- **DWIFslPreproc**: Configurable `-rpe_*` options based on distortion strategy

### Container Mount Points (defaults in argument_parser.py)

| Mount | Default | Usage |
|-------|---------|-------|
| `--bids-dir` | `/data` | BIDS dataset (read-only) |
| `--freesurfer-dir` | `/freesurfer` | FreeSurfer derivatives (read-only) |
| `--output-dir` | `/out` | Pipeline outputs (read-write) |
| `--work-dir` | `/tmp/work` | Nipype intermediate files |

### Known Issues

No critical bugs. Previous reports of import/hardcoding issues in `reader.py` were false — `DistortionStrategy` is imported at line 6 and `self.freesurfer_dir` is used correctly.

### Implemented Features (previously reported as missing)

- **mtnormalise**: Fully implemented in `workflow_builder.py` (1-tissue single-shell, 3-tissue multi-shell)
- **DK + Destrieux atlas connectomes**: `tck2connectome` with `labelconvert` wired for both atlases via `_add_parcellation_pipeline` in `workflow_builder.py`
- **Nipype MultiProc plugin**: `__main__.py` passes `plugin='MultiProc'` with `n_procs` from config
- **LUT discovery**: `utils/constants.py` has `find_mrtrix_lut_dir()` for locating MRtrix3 label files
- **Output folder naming**: Uses `sub-{subject}_ses-{session}` format via `processing_config.py`

### Incomplete/Stub Features (vs planning_docs/ spec)

- `infrastructure/reporting/` (qc_generator, html_renderer): empty files
- `application/executors/pipeline_executor.py`: empty — `__main__.py` calls `workflow.run()` directly
- `application/builders/workflow_director.py`: empty — the WorkflowDirector class lives in `workflow_builder.py` instead
- `utils/paths.py`, `utils/logging.py`: empty
- **Brainnetome atlas**: TODO in `workflow_builder.py` — DK + Destrieux are wired, Brainnetome requires volumetric atlas + ANTs warp (deferred)
- **Provenance/metrics JSON output**: not implemented
- **`--dry-run` CLI flag**: planned but not in argument_parser.py
- NHP strategies: not implemented (only HUMAN strategies registered)
- `connectivity_shared` integration: not started

### Custom Exception Hierarchy

All in `domain/exceptions/errors.py`: `PipelineError` base → `BidsValidationError`, `FreeSurferError`, `MissingMetadataError`, `ConfigurationError`, `WorkflowBuildError`, `WorkflowExecutionError`, `ReportGenerationError`.
