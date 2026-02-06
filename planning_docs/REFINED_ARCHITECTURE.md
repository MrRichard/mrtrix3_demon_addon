# MRtrix3 DWI Pipeline - Refined Architecture (v2)

## Updated Based on Feedback

This document incorporates the clarifications and design decisions made during architectural review.

---

## Critical Design Decisions ✅

### 1. FreeSurfer: MANDATORY Requirement

**Decision:** Pipeline FAILS if FreeSurfer recon-all is not complete.

```python
# Strict validation - no exceptions
if not freesurfer_validator.validate(subject, session):
    logger.error("FreeSurfer recon required but not found")
    logger.error("Please run recon-all first")
    sys.exit(1)
```

**Rationale:**
- FreeSurfer is a prerequisite step, not optional
- Failing fast saves compute time
- Clear error messages guide users to fix the problem
- Simplifies the pipeline (no fallback strategies needed)

**Required FreeSurfer Files:**
- `mri/aparc+aseg.mgz` - Desikan-Killiany parcellation (REQUIRED)
- `mri/brain.mgz` - Brain extracted T1 (REQUIRED)
- `mri/aparc.a2009s+aseg.mgz` - Destrieux parcellation (recommended)

---

### 2. Multi-Dimensional Strategy Pattern

**Decision:** Support BOTH shell type AND species with future extensibility

```python
# Strategy matrix: Species × Shell Type
strategy_map = {
    (Species.HUMAN, ShellType.SINGLE_SHELL): HumanSingleShellStrategy,
    (Species.HUMAN, ShellType.MULTI_SHELL): HumanMultiShellStrategy,
    (Species.NHP, ShellType.SINGLE_SHELL): NhpSingleShellStrategy,  # Future
    (Species.NHP, ShellType.MULTI_SHELL): NhpMultiShellStrategy,    # Future
}
```

**Current Support:**
- ✅ Human + Single-shell (DTI)
- ✅ Human + Multi-shell (NODDI, DKI-ready)

**Future Extensions:**
- 🔜 NHP + Single-shell
- 🔜 NHP + Multi-shell
- 🔜 Other species (rodent, etc.)
- 🔜 Other models (DKI, NODDI, etc.)

**Key Differences:**

| Aspect | Human | NHP (Future) |
|--------|-------|--------------|
| Brain extraction | dwi2mask / FSL bet | DeepBET (NHP model) |
| Parcellations | FreeSurfer required | NHP atlases |
| Template | MNI152 | D99 Macaque |
| 5TT generation | 5ttgen fsl | 5ttgen fsl (tuned) |
| Validation | Requires FreeSurfer | No FreeSurfer |

---

### 3. Output Structure (BIDS Derivatives)

**Decision:** Full BIDS derivatives compliance

```
<bids_dataset>/
└── derivatives/
    ├── freesurfer/              # Input (from previous step)
    │   └── sub-01/
    │       └── mri/
    │           ├── aparc+aseg.mgz
    │           └── brain.mgz
    └── dwi-pipeline/            # Our outputs
        ├── dataset_description.json
        └── sub-01/
            └── ses-01/
                └── dwi/
                    ├── *_connectome.csv          # PRIMARY OUTPUTS
                    ├── *_tractography.tck        # Tractography
                    ├── *_metrics.json            # Summary
                    ├── *_qc-report.html          # QC
                    ├── *_provenance.json         # Provenance
                    └── figures/                  # QC images
```

**Naming Convention:**
```
sub-<label>_ses-<label>_[space-<label>]_[atlas-<label>]_[desc-<label>]_<suffix>

Examples:
sub-01_ses-01_space-dwi_desc-preproc_dwi.nii.gz
sub-01_ses-01_atlas-Brainnetome_desc-count_connectome.csv
sub-01_ses-01_space-dwi_desc-sift1M_tractography.tck
```

---

### 4. Parallel Processing

**Decision:** Handle internally via Nipype MultiProc plugin

```bash
# Default: 4 threads
docker run dwi-pipeline:latest sub-01 ses-01

# Custom: 16 threads
docker run dwi-pipeline:latest sub-01 ses-01 --n-threads 16

# Maximum recommended: 32 threads
docker run dwi-pipeline:latest sub-01 ses-01 --n-threads 32
```

**Implementation:**
```python
workflow.run(
    plugin='MultiProc',
    plugin_args={'n_procs': config.n_threads}
)
```

**Benefits:**
- Simple user interface
- Nipype handles parallel execution
- No external scheduler required
- Works on single cluster node

---

### 5. Atlas & Parameter Management

**Decision:** 
- Atlases BAKED INTO container image
- ALL parameters extracted from BIDS JSON sidecars

**Container Includes:**
```
/opt/atlases/
├── Brainnetome.nii.gz
├── Brainnetome_labels.txt
├── MNI152_T2_relx.nii
└── README.md
```

**BIDS JSON Extraction:**
```json
// sub-01_ses-01_dir-AP_dwi.json
{
  "PhaseEncodingDirection": "j",        // → dwifslpreproc -pe_dir
  "TotalReadoutTime": 0.0936,           // → dwifslpreproc -readout_time
  "EchoTime": 0.089,                    // → QC reporting
  "RepetitionTime": 8.3,                // → QC reporting
  "Manufacturer": "Siemens"             // → Provenance
}

// Fieldmap JSON (if present)
{
  "EchoTime1": 0.00492,
  "EchoTime2": 0.00738
}
// DELTA_TE = 0.00246s = 2.46ms → fsl_prepare_fieldmap
```

**Parameter Validation:**
```python
class BidsMetadataExtractor:
    def extract_pe_direction(self, json_data) -> str:
        """Extract phase encoding direction"""
        if 'PhaseEncodingDirection' in json_data:
            return json_data['PhaseEncodingDirection']
        elif 'InPlanePhaseEncodingDirection' in json_data:
            # Convert COL/ROW to i/j
            return self._convert_pe_direction(json_data['InPlanePhaseEncodingDirection'])
        else:
            raise ValueError("No phase encoding direction in JSON sidecar")
    
    def extract_readout_time(self, json_data) -> float:
        """Extract total readout time"""
        if 'TotalReadoutTime' in json_data:
            return json_data['TotalReadoutTime']
        elif 'EffectiveEchoSpacing' in json_data and 'ReconMatrixPE' in json_data:
            # Calculate from echo spacing
            return json_data['EffectiveEchoSpacing'] * (json_data['ReconMatrixPE'] - 1)
        else:
            raise ValueError("Cannot determine total readout time")
```

**Key Principle:** ZERO hardcoded parameters. Everything from BIDS.

---

## Updated Container Interface

### Command Syntax

```bash
docker run --rm \
  -v <bids_dir>:/data:ro \
  -v <freesurfer_dir>:/freesurfer:ro \
  -v <output_dir>:/out \
  dwi-pipeline:latest \
  <subject> <session> [OPTIONS]
```

### Required Arguments

- `subject` - Subject ID (e.g., sub-01)
- `session` - Session ID (e.g., ses-01)

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n-threads N` | 4 | Number of parallel threads (max 32) |
| `--species {human\|nhp}` | human | Species (NHP support future) |
| `--rerun` | False | Force rerun (ignore cache) |
| `--dry-run` | False | Build workflow only |
| `--verbose, -v` | 0 | Verbosity (-v, -vv, -vvv) |

### Usage Examples

**Basic:**
```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01
```

**High-performance:**
```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01 \
  --n-threads 16 \
  --verbose
```

**SLURM batch:**
```bash
#!/bin/bash
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --array=1-100

subjects=(sub-01 sub-02 ... sub-100)
subject=${subjects[$SLURM_ARRAY_TASK_ID]}

singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/derivatives/dwi:/out \
  dwi-pipeline.sif \
  $subject ses-01 \
  --n-threads 16
```

---

## Workflow Conditional Logic

### Node Inclusion Matrix

| Node | Single-Shell | Multi-Shell | Notes |
|------|-------------|-------------|-------|
| mrconvert | ✓ | ✓ | Always |
| dwidenoise | ✓ | ✓ | Always |
| mrdegibbs | ✓ | ✗ | Single-shell only |
| dwifslpreproc | ✓ | ✓ | Always (strategy varies) |
| dwibiascorrect | ✓ | ✓ | Always |
| dwi2mask | ✓ | ✓ | Always |
| dwi2response tournier | ✓ | ✗ | Single-shell |
| dwi2response dhollander | ✗ | ✓ | Multi-shell |
| dwi2fod csd | ✓ | ✗ | Single-shell |
| dwi2fod msmt_csd | ✗ | ✓ | Multi-shell |
| mtnormalise (1 tissue) | ✓ | ✗ | Single-shell |
| mtnormalise (3 tissues) | ✗ | ✓ | Multi-shell |
| tckgen | ✓ | ✓ | Cutoff varies |
| tcksift | ✓ | ✓ | Always |
| FreeSurfer connectomes | ✓ | ✓ | Always (mandatory) |
| Brainnetome connectome | ✓ | ✓ | Always |

### Parameter Differences

| Parameter | Single-Shell | Multi-Shell |
|-----------|-------------|-------------|
| FOD cutoff | 0.1 | 0.06 |
| Response function | tournier | dhollander |
| FOD algorithm | csd | msmt_csd |
| mrdegibbs | Yes | No |
| Tissues | WM only | WM+GM+CSF |

---

## Validation Strategy

### Pre-Execution Checks

```python
def validate_pipeline_inputs():
    """Strict validation before any processing"""
    
    # 1. BIDS structure
    if not bids_validator.validate_structure():
        fail("Invalid BIDS structure")
    
    # 2. Required files
    if not dwi_files_exist():
        fail("Missing DWI files")
    
    if not anat_files_exist():
        fail("Missing anatomical files")
    
    # 3. FreeSurfer (MANDATORY)
    if not freesurfer_validator.validate():
        fail("""
        FreeSurfer recon required but not found.
        
        Expected: /freesurfer/sub-XX[/ses-YY]/mri/
        Required files:
          - aparc+aseg.mgz
          - brain.mgz
        
        Please run FreeSurfer recon-all first.
        """)
    
    # 4. BIDS JSON metadata
    if not validate_dwi_json():
        fail("Missing required metadata in DWI JSON")
    
    # All checks passed
    return True
```

### Error Messages

Clear, actionable error messages:

```
ERROR: FreeSurfer recon required but not found

Expected location:
  /freesurfer/sub-01/ses-01/mri/

Required files:
  ✗ aparc+aseg.mgz - NOT FOUND
  ✗ brain.mgz - NOT FOUND

This pipeline requires a complete FreeSurfer recon-all run.
Please ensure FreeSurfer processing has completed successfully
before running this pipeline.

To run FreeSurfer:
  recon-all -subject sub-01 -i T1.nii.gz -all

For more information:
  https://surfer.nmr.mgh.harvard.edu/fswiki/recon-all
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure (Weeks 1-2) ✅
- [x] Design approved
- [ ] Repository setup with package structure
- [ ] Domain models (BidsLayout, DwiData, ProcessingConfig)
- [ ] Enums (Species, ShellType, DistortionStrategy)
- [ ] Validation rules (strict FreeSurfer checking)
- [ ] Unit tests for domain layer

### Phase 2: BIDS & Parameter Extraction (Weeks 3-4)
- [ ] BidsReader implementation
- [ ] BIDS JSON metadata extractor
- [ ] Parameter validation (PE direction, readout time, etc.)
- [ ] FreeSurfer validator (strict checking)
- [ ] Integration tests with real data

### Phase 3: Multi-Dimensional Strategies (Weeks 5-6)
- [ ] ProcessingStrategy base class
- [ ] HumanSingleShellStrategy
- [ ] HumanMultiShellStrategy
- [ ] StrategyFactory with registry
- [ ] Unit tests with mocked strategies

### Phase 4: Nipype Workflow Construction (Weeks 7-8)
- [ ] WorkflowBuilder
- [ ] MRtrix3 Nipype interfaces
- [ ] FSL Nipype interfaces
- [ ] ANTs Nipype interfaces
- [ ] Conditional node inclusion logic
- [ ] Workflow tests

### Phase 5: CLI & Execution (Week 9)
- [ ] CLI argument parser
- [ ] Threading control (--n-threads)
- [ ] Logging configuration
- [ ] Pipeline executor
- [ ] Error handling & user feedback

### Phase 6: Container (Week 10)
- [ ] Dockerfile with MRtrix3, FSL, ANTs
- [ ] Atlas installation (/opt/atlases)
- [ ] Container build & optimization
- [ ] Singularity recipe
- [ ] Container testing

### Phase 7: QC & Reporting (Week 11)
- [ ] QC metrics calculation
- [ ] HTML report generation
- [ ] Provenance tracking
- [ ] Summary JSON generation

### Phase 8: Testing & Documentation (Week 12)
- [ ] Full pipeline test with real data
- [ ] Validation against current pipeline
- [ ] README and usage documentation
- [ ] API documentation
- [ ] Example datasets

---

## Key Questions Resolved ✅

1. **FreeSurfer requirement?** → MANDATORY, fail if missing
2. **Processing scope?** → Single container, multi-shell + species support
3. **Output organization?** → BIDS derivatives: `derivatives/dwi-pipeline/sub-XX/ses-YY/dwi/`
4. **Parallel processing?** → Internal via Nipype, `--n-threads` CLI option (default 4)
5. **Atlas management?** → Baked into container, parameters from BIDS JSON

---

## Next Steps

1. ✅ Review refined architecture
2. ✅ Confirm design decisions
3. 🔜 Begin Phase 1 implementation (domain models)
4. 🔜 Set up development environment
5. 🔜 Create sample test data

---

## Summary

The refined architecture provides:

✅ **Container-native** - Runs standalone in Docker/Singularity  
✅ **Clean architecture** - Testable, maintainable, extensible  
✅ **BIDS compliant** - Standard input/output formats  
✅ **Strict validation** - FreeSurfer required, fail fast  
✅ **Multi-dimensional** - Species × Shell type strategies  
✅ **Parameter-free** - All params from BIDS JSON  
✅ **Self-contained** - Atlases in container  
✅ **Parallel-ready** - Thread control via CLI  
✅ **Future-proof** - Easy to add NHP, other models  

The design preserves all existing logic while making it production-ready, testable, and maintainable.
