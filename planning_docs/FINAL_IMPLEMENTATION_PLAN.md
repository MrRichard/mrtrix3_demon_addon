# MRtrix3 DWI Pipeline - Final Implementation Plan

## Design Decisions (Confirmed)

### 1. FreeSurfer: MANDATORY ✅
- Pipeline **FAILS** if FreeSurfer recon is missing
- No fallback, no workarounds
- Clear error message directing user to complete FreeSurfer first

### 2. Species Support ✅
- **Current**: Human (single-shell + multi-shell)
- **Future**: Non-human primate (NHP)
- **Design**: Multi-dimensional Strategy pattern enables easy extension

### 3. Output Structure ✅
```
<bids_dataset>/
├── sub-01/
│   └── ses-01/
│       └── dwi/
│           └── sub-01_ses-01_dir-AP_dwi.nii.gz
└── derivatives/
    ├── freesurfer/              # Required input
    │   └── sub-01/
    │       └── mri/
    └── sub-01_ses-01/           # Our outputs
        ├── *_connectome.csv
        ├── *_tractography.tck
        ├── *_metrics.json
        └── *_qc-report.html
```

### 4. Threading ✅
- **Internal**: Nipype MultiProc plugin
- **Default**: 4 threads
- **Range**: 1-32 threads
- **CLI**: `--nthreads N`

### 5. Configuration ✅
- **Container**: Simple CLI interface only
- **Parameters**: Extracted from BIDS JSON sidecars
- **Batch Processing**: External (not in container)
- **Atlases**: Shipped in container image

---

## Container Interface

### Basic Command
```bash
docker run --rm \
  -v /path/to/bids:/data:ro \
  -v /path/to/freesurfer:/freesurfer:ro \
  -v /path/to/bids/derivatives:/out \
  dwi-pipeline:latest \
  sub-01 ses-01
```

### With Options
```bash
docker run --rm \
  -v /path/to/bids:/data:ro \
  -v /path/to/freesurfer:/freesurfer:ro \
  -v /path/to/bids/derivatives:/out \
  dwi-pipeline:latest \
  sub-01 ses-01 \
  --nthreads 16 \
  --rerun \
  --verbose
```

### Expected Directory Structure

**Input (BIDS):**
```
/data/
└── sub-01/
    └── ses-01/
        ├── dwi/
        │   ├── sub-01_ses-01_dir-AP_dwi.nii.gz
        │   ├── sub-01_ses-01_dir-AP_dwi.bval
        │   ├── sub-01_ses-01_dir-AP_dwi.bvec
        │   └── sub-01_ses-01_dir-AP_dwi.json  ← Parameters here
        └── anat/
            └── sub-01_ses-01_T1w.nii.gz
```

**Input (FreeSurfer):**
```
/freesurfer/
└── sub-01/
    └── mri/
        ├── aparc+aseg.mgz        ← REQUIRED
        ├── brain.mgz             ← REQUIRED
        └── aparc.a2009s+aseg.mgz ← Optional
```

**Output:**
```
/out/
└── sub-01_ses-01/
    ├── sub-01_ses-01_atlas-Brainnetome_desc-count_connectome.csv
    ├── sub-01_ses-01_atlas-Brainnetome_desc-scaled_connectome.csv
    ├── sub-01_ses-01_atlas-FreeSurferDK_desc-count_connectome.csv
    ├── sub-01_ses-01_atlas-FreeSurferDK_desc-scaled_connectome.csv
    ├── sub-01_ses-01_space-dwi_desc-sift1M_tractography.tck
    ├── sub-01_ses-01_metrics.json
    ├── sub-01_ses-01_qc-report.html
    └── figures/
        └── *.png
```

---

## BIDS JSON Parameter Extraction

### Required Parameters
From `sub-01_ses-01_dir-AP_dwi.json`:

```json
{
  "PhaseEncodingDirection": "j",     // → dwifslpreproc -pe_dir
  "TotalReadoutTime": 0.0936         // → dwifslpreproc -readout_time
}
```

**OR** calculated from:
```json
{
  "EffectiveEchoSpacing": 0.00039,
  "ReconMatrixPE": 240
}
// TotalReadoutTime = 0.00039 × (240 - 1) = 0.093
```

### Optional Parameters
```json
{
  "EchoTime": 0.089,                 // → QC reporting
  "RepetitionTime": 8.3,             // → QC reporting
  "Manufacturer": "Siemens",         // → Provenance
  "ManufacturersModelName": "Prisma" // → Provenance
}
```

### Fieldmap Parameters (if available)
From `sub-01_ses-01_phasediff.json`:

```json
{
  "EchoTime1": 0.00492,
  "EchoTime2": 0.00738
}
// DELTA_TE = 0.00738 - 0.00492 = 0.00246 s = 2.46 ms
// → Used for fsl_prepare_fieldmap
```

---

## Auto-Detection Logic

### 1. Shell Configuration Detection
```python
def detect_shell_type(bval_file: Path) -> ShellType:
    """
    Detect single-shell vs multi-shell from bval file
    
    Single-shell: One non-zero b-value (e.g., b=0, b=1000)
    Multi-shell: Multiple non-zero b-values (e.g., b=0, b=1000, b=2000)
    """
    bvals = np.loadtxt(bval_file)
    unique_bvals = np.unique(bvals[bvals > 50])  # Exclude b=0
    
    if len(unique_bvals) == 1:
        return ShellType.SINGLE_SHELL
    else:
        return ShellType.MULTI_SHELL
```

### 2. Distortion Correction Detection
```python
def detect_distortion_correction(layout: BidsLayout) -> DistortionStrategy:
    """
    Detect distortion correction strategy from available data
    
    Priority:
    1. Reverse phase encoding (RPE) pair
    2. Fieldmap
    3. None (no correction possible)
    """
    if layout.dwi_pa exists:
        return DistortionStrategy.RPE_PAIR
    elif layout.phasediff exists or layout.phase1 exists:
        return DistortionStrategy.FIELDMAP
    else:
        return DistortionStrategy.NONE
```

### 3. Strategy Selection
```python
def select_strategy(shell_type: ShellType, species: Species) -> ProcessingStrategy:
    """
    Select appropriate processing strategy
    
    Current:
    - (HUMAN, SINGLE_SHELL) → HumanSingleShellStrategy
    - (HUMAN, MULTI_SHELL) → HumanMultiShellStrategy
    
    Future:
    - (NHP, SINGLE_SHELL) → NhpSingleShellStrategy
    - (NHP, MULTI_SHELL) → NhpMultiShellStrategy
    """
    strategy_map = {
        (Species.HUMAN, ShellType.SINGLE_SHELL): HumanSingleShellStrategy,
        (Species.HUMAN, ShellType.MULTI_SHELL): HumanMultiShellStrategy,
    }
    
    return strategy_map[(species, shell_type)]()
```

---

## Processing Strategy Matrix

|                | Single-Shell         | Multi-Shell           |
|----------------|----------------------|-----------------------|
| **Response**   | tournier             | dhollander            |
| **FOD**        | csd                  | msmt_csd              |
| **Degibbs**    | Yes                  | No                    |
| **Cutoff**     | 0.1                  | 0.06                  |
| **Tissues**    | WM only              | WM + GM + CSF         |
| **Normalize**  | 1 tissue             | 3 tissues             |

---

## External Batch Processing Example

**Note**: This is handled OUTSIDE the container by you, but here's how it works:

```python
# batch_config.json
{
  "subjects": [
    {"subject": "sub-01", "session": "ses-01", "nthreads": 16},
    {"subject": "sub-02", "session": "ses-01", "nthreads": 16},
    {"subject": "sub-03", "session": "ses-01", "nthreads": 8}
  ],
  "bids_dir": "/data/bids",
  "freesurfer_dir": "/data/freesurfer",
  "output_dir": "/data/bids/derivatives"
}

# batch_runner.py (YOUR external script)
import json
import subprocess

with open('batch_config.json') as f:
    config = json.load(f)

for subj in config['subjects']:
    cmd = [
        'docker', 'run', '--rm',
        '-v', f'{config["bids_dir"]}:/data:ro',
        '-v', f'{config["freesurfer_dir"]}:/freesurfer:ro',
        '-v', f'{config["output_dir"]}:/out',
        'dwi-pipeline:latest',
        subj['subject'],
        subj['session'],
        '--nthreads', str(subj['nthreads'])
    ]
    
    subprocess.run(cmd, check=True)
```

**Or with SLURM array:**

```bash
#!/bin/bash
#SBATCH --array=1-100
#SBATCH --cpus-per-task=16

subjects=(sub-01 sub-02 ... sub-100)
subject=${subjects[$SLURM_ARRAY_TASK_ID]}

singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/bids/derivatives:/out \
  dwi-pipeline.sif \
  $subject ses-01 \
  --nthreads $SLURM_CPUS_PER_TASK
```

---

## Validation Flow

```
1. Check BIDS structure
   ├─ Validate subject/session directories
   ├─ Find DWI files
   ├─ Find anatomical files
   └─ Find sidecar JSON files

2. Extract and validate BIDS metadata
   ├─ PhaseEncodingDirection (required)
   ├─ TotalReadoutTime (required, or calculate)
   └─ Other acquisition parameters

3. Validate FreeSurfer (CRITICAL)
   ├─ Check directory exists
   ├─ Verify aparc+aseg.mgz (REQUIRED)
   ├─ Verify brain.mgz (REQUIRED)
   └─ FAIL if missing

4. Auto-detect configuration
   ├─ Shell type (single/multi)
   ├─ Distortion correction strategy
   └─ Available parcellations

5. Select processing strategy
   └─ Based on shell type (+ species in future)

6. Build workflow

7. Execute workflow

8. Generate outputs
```

**If FreeSurfer validation fails:**
```
ERROR: FreeSurfer recon required but not found

Expected: /freesurfer/sub-01/mri/

Required files:
  ✗ aparc+aseg.mgz - NOT FOUND
  ✗ brain.mgz - NOT FOUND

FreeSurfer recon-all must be completed before running this pipeline.

To run FreeSurfer:
  recon-all -subject sub-01 -i T1.nii.gz -all

Exit code: 2
```

---

## 12-Week Implementation Plan

### Phase 1: Foundation (Weeks 1-2)
- [ ] Repository setup
- [ ] Domain models (BidsLayout, DwiData, ProcessingConfig)
- [ ] Enums (ShellType, DistortionStrategy, Species)
- [ ] Validation framework (BIDS, FreeSurfer, metadata)
- [ ] Unit tests (100% coverage of domain layer)

**Deliverable**: Pure Python domain layer with zero external dependencies

### Phase 2: BIDS Infrastructure (Weeks 3-4)
- [ ] BidsReader (discover BIDS files)
- [ ] BidsMetadataExtractor (parse JSON sidecars)
- [ ] FreeSurferValidator (strict validation)
- [ ] Auto-detection logic (shell type, distortion correction)
- [ ] Integration tests with real BIDS data

**Deliverable**: Working BIDS discovery and validation

### Phase 3: Strategy Pattern (Weeks 5-6)
- [ ] ProcessingStrategy base class
- [ ] HumanSingleShellStrategy implementation
- [ ] HumanMultiShellStrategy implementation
- [ ] StrategyFactory with registry
- [ ] Unit tests with mocked strategies

**Deliverable**: Complete strategy pattern implementation

### Phase 4: Nipype Workflows (Weeks 7-8)
- [ ] WorkflowBuilder
- [ ] MRtrix3 Nipype interfaces (all commands)
- [ ] FSL Nipype interfaces (required commands)
- [ ] ANTs Nipype interfaces (registration)
- [ ] Conditional node inclusion
- [ ] Workflow execution tests

**Deliverable**: Complete Nipype workflow construction

### Phase 5: CLI & Execution (Week 9)
- [ ] Argument parser (subject, session, --nthreads, etc.)
- [ ] Logging configuration
- [ ] PipelineExecutor
- [ ] Error handling with clear messages
- [ ] CLI integration tests

**Deliverable**: Working command-line interface

### Phase 6: Containerization (Week 10)
- [ ] Dockerfile (MRtrix3 + FSL + ANTs + Python)
- [ ] Install atlases (Brainnetome, MNI152)
- [ ] Optimize image size
- [ ] Singularity recipe
- [ ] Container build/test pipeline

**Deliverable**: Working Docker + Singularity containers

### Phase 7: QC & Reporting (Week 11)
- [ ] QC metric calculation
- [ ] HTML report template
- [ ] Figure generation
- [ ] Provenance JSON
- [ ] Summary metrics JSON

**Deliverable**: Comprehensive QC reporting

### Phase 8: Testing & Documentation (Week 12)
- [ ] End-to-end test with real data
- [ ] Validation against current pipeline
- [ ] README with usage examples
- [ ] API documentation
- [ ] Tutorial notebook

**Deliverable**: Production-ready pipeline with docs

---

## Testing Strategy

### Unit Tests
```python
# Test domain models
def test_shell_detection_single_shell():
    bvals = np.array([0, 1000, 1000, 1000])
    assert detect_shell_type(bvals) == ShellType.SINGLE_SHELL

# Test metadata extraction
def test_extract_readout_time_from_trt():
    json_data = {"TotalReadoutTime": 0.0936}
    assert extract_readout_time(json_data) == 0.0936

# Test strategy selection
def test_strategy_selection_human_single():
    strategy = select_strategy(ShellType.SINGLE_SHELL, Species.HUMAN)
    assert isinstance(strategy, HumanSingleShellStrategy)
```

### Integration Tests
```python
# Test with real BIDS data
def test_bids_discovery():
    reader = BidsReader('/data/test_bids')
    layout = reader.discover('sub-01', 'ses-01')
    assert layout.dwi_ap.exists()
    assert layout.shell_config == ShellType.SINGLE_SHELL

# Test FreeSurfer validation
def test_freesurfer_validation_pass():
    validator = FreeSurferValidator('/data/freesurfer')
    is_valid, errors = validator.validate('sub-01', 'ses-01')
    assert is_valid
    assert len(errors) == 0
```

### End-to-End Tests
```python
# Test full pipeline
def test_full_pipeline_single_shell():
    result = run_container(
        subject='sub-test01',
        session='ses-01',
        nthreads=4
    )
    
    assert result.exit_code == 0
    assert result.connectomes_exist()
    assert result.qc_report_exists()
```

---

## Key Benefits

### For You (Developer)
✅ Clean architecture → Easy to maintain  
✅ Strategy pattern → Easy to add NHP support  
✅ Type-safe Python → Catch errors early  
✅ Comprehensive tests → Confident refactoring  
✅ Container-native → Reproducible builds  

### For Users
✅ Simple CLI → Easy to use  
✅ Auto-detection → No config needed  
✅ BIDS compliant → Standard formats  
✅ Clear errors → Easy to debug  
✅ QC reports → Visual validation  

### For Science
✅ Reproducible → Docker/Singularity  
✅ Provenance → Full processing history  
✅ Standards → BIDS derivatives  
✅ Extensible → Future processing methods  

---

## Ready to Start?

All design decisions are finalized. The architecture:

1. ✅ Fails if FreeSurfer missing
2. ✅ Supports single/multi-shell (human)
3. ✅ Extensible for NHP
4. ✅ Outputs to derivatives/sub-XX_ses-YY/
5. ✅ Threading via --nthreads
6. ✅ Parameters from BIDS JSON
7. ✅ Atlases in container

**Recommend starting with Phase 1** (domain models) - this gives you the foundation and you can iterate from there.

Would you like me to:
- A) Start implementing Phase 1 (domain models + enums)?
- B) Create example test data?
- C) Set up the repository structure?
- D) Something else?
