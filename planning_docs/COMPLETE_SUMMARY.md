# MRtrix3 DWI Pipeline - Complete Architecture Summary

## Executive Summary

This document provides a complete overview of the refactored MRtrix3 DWI pipeline architecture, incorporating all design decisions and clarifications.

---

## Architecture at a Glance

```
┌────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Python Application                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  CLI (Presentation)                            │  │  │
│  │  │  • Argument parsing                            │  │  │
│  │  │  • Validation orchestration                    │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  Application (Business Logic)                  │  │  │
│  │  │  • Multi-dimensional Strategy Pattern          │  │  │
│  │  │  • Workflow Factory                            │  │  │
│  │  │  • Workflow Builder                            │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  Domain (Core Models)                          │  │  │
│  │  │  • BidsLayout                                  │  │  │
│  │  │  • DwiData                                     │  │  │
│  │  │  • ProcessingConfig                            │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │  Infrastructure (Tool Wrappers)                │  │  │
│  │  │  • BIDS Reader                                 │  │  │
│  │  │  • Nipype Interfaces                           │  │  │
│  │  │  • QC Report Generator                         │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              External Tools                           │  │
│  │  • MRtrix3     • FSL      • ANTs                     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Atlases (Baked In)                       │  │
│  │  • Brainnetome  • MNI152 Template                    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
         ↓                ↓                    ↓
    /data (RO)      /freesurfer (RO)      /out (RW)
```

---

## Complete Design Decisions

### 1. FreeSurfer: Mandatory Requirement ✅

```python
# FAIL FAST if FreeSurfer missing
if not freesurfer_exists():
    print("""
    ERROR: FreeSurfer recon required
    
    Expected: /freesurfer/sub-XX/mri/aparc+aseg.mgz
    
    Run FreeSurfer first:
      recon-all -subject sub-XX -i T1.nii.gz -all
    """)
    sys.exit(1)
```

### 2. Multi-Dimensional Strategy Matrix ✅

```
                Single-Shell              Multi-Shell
              ┌──────────────────┬──────────────────┐
    Human     │ HumanSingleShell │ HumanMultiShell  │
              │ Strategy         │ Strategy         │
              │                  │                  │
              │ • tournier       │ • dhollander     │
              │ • csd            │ • msmt_csd       │
              │ • mrdegibbs ✓    │ • mrdegibbs ✗    │
              │ • cutoff 0.1     │ • cutoff 0.06    │
              ├──────────────────┼──────────────────┤
    NHP       │ NhpSingleShell   │ NhpMultiShell    │
    (Future)  │ Strategy         │ Strategy         │
              │                  │                  │
              │ • tournier       │ • dhollander     │
              │ • DeepBET        │ • DeepBET        │
              │ • NHP atlases    │ • NHP atlases    │
              └──────────────────┴──────────────────┘
```

### 3. BIDS Derivatives Output ✅

```
derivatives/
└── dwi-pipeline/
    ├── dataset_description.json
    └── sub-01/
        └── ses-01/
            └── dwi/
                ├── *_atlas-Brainnetome_desc-count_connectome.csv    ← PRIMARY
                ├── *_atlas-Brainnetome_desc-scaled_connectome.csv   ← PRIMARY
                ├── *_atlas-FreeSurferDK_desc-count_connectome.csv   ← PRIMARY
                ├── *_atlas-FreeSurferDK_desc-scaled_connectome.csv  ← PRIMARY
                ├── *_space-dwi_desc-sift1M_tractography.tck
                ├── *_metrics.json
                ├── *_qc-report.html
                └── *_provenance.json
```

### 4. Threading Control ✅

```bash
# Default: 4 threads
docker run dwi-pipeline:latest sub-01 ses-01

# Custom: 16 threads  
docker run dwi-pipeline:latest sub-01 ses-01 --n-threads 16

# Implemented via:
workflow.run(plugin='MultiProc', plugin_args={'n_procs': n_threads})
```

### 5. Parameter Extraction from BIDS JSON ✅

```json
// sub-01_ses-01_dir-AP_dwi.json
{
  "PhaseEncodingDirection": "j",     → dwifslpreproc -pe_dir j
  "TotalReadoutTime": 0.0936,        → dwifslpreproc -readout_time 0.0936
  "Manufacturer": "Siemens"          → Provenance tracking
}

// sub-01_ses-01_phasediff.json (if fieldmaps present)
{
  "EchoTime1": 0.00492,
  "EchoTime2": 0.00738                → DELTA_TE = 2.46ms
}
```

**NO hardcoded parameters. ALL from BIDS metadata.**

---

## Complete Workflow Logic

### Processing Flow

```
1. Validate Inputs
   ├─ Check BIDS structure
   ├─ Verify DWI files + JSON sidecars
   ├─ Verify T1w file
   └─ Verify FreeSurfer (MANDATORY)
        └─ FAIL if missing

2. Detect Configuration
   ├─ Read bval file → Detect shell type
   ├─ Read JSON → Extract PE direction, readout time
   ├─ Check for reverse PE → Distortion correction strategy
   └─ Species (human default, NHP future)

3. Select Strategy
   └─ strategy = strategy_map[(species, shell_type)]
        ├─ (HUMAN, SINGLE_SHELL) → HumanSingleShellStrategy
        ├─ (HUMAN, MULTI_SHELL) → HumanMultiShellStrategy
        ├─ (NHP, SINGLE_SHELL) → NhpSingleShellStrategy (future)
        └─ (NHP, MULTI_SHELL) → NhpMultiShellStrategy (future)

4. Build Workflow
   ├─ Create preprocessing nodes (strategy-dependent)
   ├─ Create response estimation nodes (strategy-dependent)
   ├─ Create FOD estimation nodes (strategy-dependent)
   ├─ Create tractography nodes
   └─ Create connectome nodes (FreeSurfer + Brainnetome)

5. Execute Workflow
   └─ Run with MultiProc plugin (n_threads parameter)

6. Generate Outputs
   ├─ Connectome CSVs (counts + scaled)
   ├─ Tractography files
   ├─ Metrics JSON
   ├─ QC report HTML
   └─ Provenance JSON
```

### Conditional Nodes

| Node | Condition |
|------|-----------|
| `mrdegibbs` | `if shell_type == SINGLE_SHELL` |
| `dwi2response (tournier)` | `if shell_type == SINGLE_SHELL` |
| `dwi2response (dhollander)` | `if shell_type == MULTI_SHELL` |
| `dwi2fod (csd)` | `if shell_type == SINGLE_SHELL` |
| `dwi2fod (msmt_csd)` | `if shell_type == MULTI_SHELL` |
| `b0_pair creation` | `if distortion == RPE_PAIR` |
| `fieldmap preparation` | `if distortion == FIELDMAP` |
| FreeSurfer connectomes | `ALWAYS (mandatory)` |

---

## Complete Container Specification

### Dockerfile Structure

```dockerfile
FROM ubuntu:22.04

# Install MRtrix3
RUN git clone https://github.com/MRtrix3/mrtrix3.git /opt/mrtrix3 && \
    cd /opt/mrtrix3 && ./configure && ./build

# Install FSL
RUN curl -O https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
    python3 fslinstaller.py -d /opt/fsl

# Install ANTs
RUN git clone https://github.com/ANTsX/ANTs.git /opt/ants-src && \
    cd /opt/ants-build && cmake /opt/ants-src && make -j8

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

# Copy atlases (baked into image)
COPY atlases/ /opt/atlases/
#   /opt/atlases/Brainnetome.nii.gz
#   /opt/atlases/MNI152_T2_relx.nii

# Copy application
COPY dwi_pipeline/ /app/dwi_pipeline/

# Set environment
ENV PATH="/opt/mrtrix3/bin:/opt/fsl/bin:/opt/ants/bin:$PATH"
ENV FSLDIR="/opt/fsl"

# Entry point
ENTRYPOINT ["python3", "-m", "dwi_pipeline"]
```

### Container Usage

**Basic:**
```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01
```

**With options:**
```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01 \
  --n-threads 16 \
  --verbose \
  --rerun
```

**SLURM array job:**
```bash
#!/bin/bash
#SBATCH --array=1-100
#SBATCH --cpus-per-task=16

subjects=(sub-01 sub-02 ... sub-100)
subject=${subjects[$SLURM_ARRAY_TASK_ID]}

singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/derivatives/dwi:/out \
  dwi-pipeline.sif \
  $subject ses-01 --n-threads 16
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
```python
# Domain models (pure Python, zero dependencies)
class BidsLayout:
    subject: str
    session: Optional[str]
    dwi_ap: Path
    t1w: Path
    freesurfer_dir: Path
    shell_config: ShellType
    distortion_correction: DistortionStrategy

class DwiData:
    bvals: np.ndarray
    pe_direction: str
    total_readout_time: float
    
class ProcessingConfig:
    n_threads: int = 4
    species: Species = Species.HUMAN
```

### Phase 2: Infrastructure (Weeks 3-4)
```python
# BIDS reading and parameter extraction
class BidsReader:
    def discover(self, subject, session) -> BidsLayout
    
class BidsMetadataExtractor:
    def extract_pe_direction(self, json_path) -> str
    def extract_readout_time(self, json_path) -> float
    def extract_delta_te(self, json_path) -> float

class FreeSurferValidator:
    def validate(self, subject, session) -> Tuple[bool, List[str]]
    # MANDATORY check - fail if missing
```

### Phase 3: Strategies (Weeks 5-6)
```python
# Multi-dimensional strategy pattern
class HumanSingleShellStrategy(ProcessingStrategy):
    def create_response_nodes(self):
        return [Dwi2Response(algorithm='tournier')]
    
    def create_fod_nodes(self):
        return [Dwi2Fod(algorithm='csd')]
    
    def should_apply_degibbs(self) -> bool:
        return True
    
    def get_fod_cutoff(self) -> float:
        return 0.1

class HumanMultiShellStrategy(ProcessingStrategy):
    def create_response_nodes(self):
        return [Dwi2Response(algorithm='dhollander')]
    
    def create_fod_nodes(self):
        return [Dwi2Fod(algorithm='msmt_csd')]
    
    def should_apply_degibbs(self) -> bool:
        return False
    
    def get_fod_cutoff(self) -> float:
        return 0.06
```

### Phase 4: Workflow (Weeks 7-8)
```python
# Nipype workflow construction
class WorkflowBuilder:
    def add_preprocessing(self):
        # mrconvert, denoise, degibbs (conditional), preproc, biascorrect
        if self.strategy.should_apply_degibbs():
            self.add_node('degibbs', MRDeGibbs())
    
    def add_response_estimation(self):
        nodes = self.strategy.create_response_nodes()
        for node in nodes:
            self.add_node(node.name, node)
    
    def add_fod_estimation(self):
        nodes = self.strategy.create_fod_nodes()
        for node in nodes:
            self.add_node(node.name, node)
```

### Phase 5: CLI (Week 9)
```python
# Command-line interface
parser.add_argument('subject')
parser.add_argument('session')
parser.add_argument('--n-threads', type=int, default=4)
parser.add_argument('--species', choices=['human', 'nhp'], default='human')
parser.add_argument('--rerun', action='store_true')
parser.add_argument('--verbose', '-v', action='count')
```

---

## Key Benefits

### For Users
✅ **Simple interface** - One command, no config files  
✅ **Automatic detection** - Shell type, distortion correction  
✅ **Standard output** - BIDS derivatives format  
✅ **Quality control** - HTML reports with visualizations  
✅ **Full provenance** - Complete processing history  

### For Developers
✅ **Testable** - Pure domain logic, mockable interfaces  
✅ **Maintainable** - Clean architecture, SOLID principles  
✅ **Extensible** - Easy to add species, processing types  
✅ **Type-safe** - Full type hints, mypy compatible  
✅ **Documented** - Comprehensive docstrings, examples  

### For Research
✅ **Reproducible** - Container ensures consistent environment  
✅ **Traceable** - Full provenance tracking  
✅ **Standards-compliant** - BIDS derivatives  
✅ **Future-proof** - Modular design, easy extensions  

---

## Files Created

1. **system_architecture.puml** - High-level system view
2. **layered_architecture.puml** - Clean architecture layers
3. **class_diagram.puml** - OOP design with patterns
4. **sequence_diagram.puml** - Execution flow
5. **workflow_graph.puml** - Nipype node structure
6. **package_structure.puml** - Module organization
7. **deployment_diagram.puml** - Container deployment
8. **strategy_pattern.puml** - Strategy pattern details
9. **validation_strategy.puml** - Input validation flow
10. **multi_dimensional_strategy.puml** - Multi-dimensional strategies
11. **output_structure.puml** - BIDS derivatives structure
12. **atlas_parameter_management.puml** - Atlas & parameter handling
13. **ARCHITECTURE.md** - Complete architecture document
14. **EXAMPLE_IMPLEMENTATION.md** - Code examples
15. **QUICK_REFERENCE.md** - Cheat sheet
16. **REFINED_ARCHITECTURE.md** - Updated with your feedback
17. **cli_interface.py** - Complete CLI implementation example

---

## Ready to Proceed?

The architecture is complete and addresses all your requirements:

1. ✅ FreeSurfer mandatory (strict validation)
2. ✅ Multi-shell + NHP support (extensible strategies)
3. ✅ BIDS derivatives output
4. ✅ Internal parallel processing (--n-threads)
5. ✅ Self-contained (atlases in container)
6. ✅ Parameter extraction (from BIDS JSON)

**Next step:** Begin Phase 1 implementation (domain models)?
