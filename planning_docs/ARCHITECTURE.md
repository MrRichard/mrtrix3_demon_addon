# MRtrix3 DWI Pipeline - Architectural Design Document

## Executive Summary

This document outlines the architectural design for refactoring the MRtrix3 DWI processing pipeline into a modern, container-native, Nipype-based application. The refactoring transforms a SLURM-coupled script-based pipeline into a clean, testable, object-oriented system that runs standalone in Docker/Singularity containers.

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Design Goals](#design-goals)
3. [Architectural Principles](#architectural-principles)
4. [System Architecture](#system-architecture)
5. [Design Patterns](#design-patterns)
6. [Module Structure](#module-structure)
7. [Workflow Design](#workflow-design)
8. [Container Strategy](#container-strategy)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Testing Strategy](#testing-strategy)

---

## Current State Analysis

### Strengths
- ✅ Comprehensive BIDS support with robust file discovery
- ✅ Sophisticated distortion correction detection (rpe_pair, fieldmap, none)
- ✅ Automatic shell configuration detection (single/multi-shell)
- ✅ FreeSurfer integration for multiple parcellation schemes
- ✅ Support for both human and NHP data
- ✅ Well-defined command sequences in JSON

### Pain Points
- ❌ Tight coupling to SLURM - can't run without batch system
- ❌ Singularity containers called externally, not container-native
- ❌ Mixed concerns: file discovery + command generation + job submission
- ❌ Code duplication between legacy and BIDS pipelines
- ❌ Hard to test without actually running MRtrix3 commands
- ❌ No workflow-level provenance or dependency management

---

## Design Goals

### Primary Goals

1. **Container-Native Execution**
   - Run entire pipeline inside Docker/Singularity
   - No external SLURM dependency
   - Single command execution: `docker run <inputs> <outputs> <subject>`

2. **Clean Architecture**
   - Separation of concerns (domain, application, infrastructure)
   - Testable without running actual neuroimaging tools
   - Clear dependency flow (depend on abstractions, not concretions)

3. **Nipype Integration**
   - Leverage Nipype's workflow management
   - Automatic caching and provenance tracking
   - Built-in parallel execution support

4. **Maintainability**
   - Object-oriented design with clear responsibilities
   - Design patterns for common problems
   - Comprehensive documentation and type hints

5. **Extensibility**
   - Easy to add new atlases
   - Easy to add new processing steps
   - Easy to support new distortion correction methods

### Secondary Goals

- Support both DTI (single-shell) and multi-shell processing
- Generate comprehensive QC reports
- BIDS derivatives compliance
- Backward compatibility for data processed with old pipeline

---

## Architectural Principles

### 1. Dependency Inversion Principle (DIP)

High-level modules (application logic) should not depend on low-level modules (tool wrappers). Both should depend on abstractions.

```python
# Bad: Direct dependency on MRtrix3
class WorkflowBuilder:
    def add_denoising(self):
        subprocess.run(["dwidenoise", ...])  # Hard-coded tool

# Good: Dependency on abstraction
class WorkflowBuilder:
    def __init__(self, denoise_interface: DenoiseInterface):
        self.denoise = denoise_interface
    
    def add_denoising(self):
        node = self.denoise.create_node()  # Abstract interface
```

### 2. Single Responsibility Principle (SRP)

Each class should have one reason to change.

- `BidsLayout` - Represents BIDS data structure (no file I/O)
- `BidsReader` - Reads BIDS data from filesystem
- `WorkflowBuilder` - Constructs Nipype workflows
- `WorkflowExecutor` - Executes workflows

### 3. Open/Closed Principle (OCP)

Open for extension, closed for modification.

```python
# Adding a new atlas doesn't require modifying existing code
class AtlasRegistry:
    def register(self, name: str, atlas: Atlas):
        self._atlases[name] = atlas

# New atlas added via configuration
registry.register("custom_atlas", CustomAtlas())
```

### 4. Interface Segregation Principle (ISP)

Many specific interfaces are better than one general-purpose interface.

```python
# Instead of one large interface
class PreprocessingInterface:
    def denoise(self): ...
    def degibbs(self): ...
    def distortion_correction(self): ...
    def bias_correction(self): ...

# Smaller, focused interfaces
class DenoiseInterface:
    def denoise(self): ...

class DistortionCorrectionInterface:
    def correct(self): ...
```

### 5. Liskov Substitution Principle (LSP)

Derived classes must be substitutable for their base classes.

```python
# Any ProcessingStrategy can be used interchangeably
strategy: ProcessingStrategy = SingleShellStrategy()
strategy = MultiShellStrategy()  # Can swap strategies
```

---

## System Architecture

See `system_architecture.puml` for visual diagram.

### Architecture Layers

```
┌─────────────────────────────────────────────┐
│         Presentation Layer (CLI)            │
│  - Argument parsing                         │
│  - Input validation                         │
│  - User feedback                            │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│       Application Layer (Orchestration)     │
│  - Workflow construction (Builder)          │
│  - Strategy selection (Factory)             │
│  - Processing strategies (Strategy)         │
│  - Pipeline execution                       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│        Domain Layer (Business Logic)        │
│  - BidsLayout (data structure)              │
│  - DwiData (metadata)                       │
│  - ProcessingConfig (parameters)            │
│  - Validation rules                         │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│    Infrastructure Layer (External Tools)    │
│  - BIDS file I/O                            │
│  - MRtrix3 interfaces (Nipype)              │
│  - FSL interfaces (Nipype)                  │
│  - ANTs interfaces (Nipype)                 │
│  - FreeSurfer integration                   │
│  - Report generation                        │
└─────────────────────────────────────────────┘
```

### Data Flow

1. **Input** → CLI reads BIDS dataset, FreeSurfer derivatives
2. **Discovery** → BidsReader populates BidsLayout domain model
3. **Validation** → Domain validators check data completeness
4. **Strategy Selection** → Factory determines processing approach
5. **Workflow Construction** → Builder creates Nipype workflow graph
6. **Execution** → Nipype executes workflow with caching/provenance
7. **Output** → Results written to BIDS derivatives directory
8. **Reporting** → QC report generated from outputs

---

## Design Patterns

### 1. Strategy Pattern

**Problem:** Different processing algorithms for single-shell vs multi-shell data

**Solution:** Encapsulate algorithms in separate strategy classes

```python
class ProcessingStrategy(ABC):
    @abstractmethod
    def create_response_nodes(self) -> List[Node]:
        pass
    
    @abstractmethod
    def create_fod_nodes(self) -> List[Node]:
        pass

class SingleShellStrategy(ProcessingStrategy):
    def create_response_nodes(self):
        # Uses tournier response
        return [Dwi2Response(algorithm='tournier')]
    
    def create_fod_nodes(self):
        # Uses single-shell CSD
        return [Dwi2Fod(algorithm='csd')]

class MultiShellStrategy(ProcessingStrategy):
    def create_response_nodes(self):
        # Uses dhollander response
        return [Dwi2Response(algorithm='dhollander')]
    
    def create_fod_nodes(self):
        # Uses multi-shell multi-tissue CSD
        return [Dwi2Fod(algorithm='msmt_csd')]
```

**Benefits:**
- Easy to add new strategies (e.g., NODDI, DKI)
- Testable: mock strategies for unit tests
- Clear separation of algorithm logic

See `strategy_pattern.puml` for detailed diagram.

### 2. Factory Pattern

**Problem:** Need to create appropriate workflow based on data characteristics

**Solution:** Factory method that examines data and returns correct strategy

```python
class WorkflowFactory:
    def create_workflow(
        self, 
        layout: BidsLayout,
        config: ProcessingConfig
    ) -> Workflow:
        strategy = self._determine_strategy(layout)
        builder = WorkflowBuilder(strategy, config)
        director = WorkflowDirector(builder)
        return director.construct_full_pipeline()
    
    def _determine_strategy(self, layout: BidsLayout) -> ProcessingStrategy:
        if layout.shell_config == 'single_shell':
            return SingleShellStrategy(layout)
        else:
            return MultiShellStrategy(layout)
```

**Benefits:**
- Centralized creation logic
- Easy to extend with new creation patterns
- Hides complex initialization

### 3. Builder Pattern

**Problem:** Constructing complex Nipype workflows with many conditional steps

**Solution:** Step-by-step workflow construction with method chaining

```python
class WorkflowBuilder:
    def __init__(self, strategy: ProcessingStrategy):
        self.strategy = strategy
        self.workflow = pe.Workflow(name='dwi_pipeline')
    
    def add_preprocessing(self) -> 'WorkflowBuilder':
        nodes = self.strategy.create_preprocessing_nodes()
        for node in nodes:
            self.workflow.add_nodes([node])
        return self
    
    def add_response_estimation(self) -> 'WorkflowBuilder':
        nodes = self.strategy.create_response_nodes()
        # Add nodes and connections
        return self
    
    def build(self) -> Workflow:
        return self.workflow

# Usage
workflow = (WorkflowBuilder(strategy)
    .add_preprocessing()
    .add_response_estimation()
    .add_fod_estimation()
    .add_tractography()
    .add_connectome_generation()
    .build())
```

**Benefits:**
- Fluent interface for workflow construction
- Conditional step inclusion easy to implement
- Clear workflow construction sequence

### 4. Template Method Pattern

**Problem:** Common workflow structure with variable steps

**Solution:** Base class defines workflow skeleton, subclasses override specific steps

```python
class BaseWorkflow(ABC):
    def execute(self):
        self.validate_inputs()
        self.preprocess()
        self.estimate_response()  # May vary by strategy
        self.estimate_fod()       # May vary by strategy
        self.register_anatomical()
        self.generate_tractography()
        self.generate_connectomes()
        self.create_report()
    
    @abstractmethod
    def estimate_response(self):
        pass
    
    @abstractmethod
    def estimate_fod(self):
        pass
```

### 5. Repository Pattern

**Problem:** Abstract BIDS data access from business logic

**Solution:** Repository interface for data operations

```python
class BidsRepository(ABC):
    @abstractmethod
    def find_dwi_files(self, subject: str, session: str) -> Dict:
        pass
    
    @abstractmethod
    def find_anatomical_files(self, subject: str, session: str) -> Dict:
        pass

class FilesystemBidsRepository(BidsRepository):
    def find_dwi_files(self, subject: str, session: str) -> Dict:
        # Actual file system operations
        pass
```

**Benefits:**
- Testable: mock repository for unit tests
- Can swap implementations (filesystem, database, S3)
- Centralized data access logic

---

## Module Structure

See `package_structure.puml` for visual diagram.

### Proposed Package Layout

```
dwi_pipeline/
├── __init__.py
├── __main__.py                 # Entry point: python -m dwi_pipeline
│
├── cli/                        # Presentation layer
│   ├── __init__.py
│   ├── argument_parser.py      # CLI argument parsing
│   └── config_loader.py        # Configuration file loading
│
├── domain/                     # Domain layer (pure Python)
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── bids_layout.py      # BIDS data structure
│   │   ├── dwi_data.py         # DWI metadata
│   │   └── processing_config.py # Processing parameters
│   ├── enums/
│   │   ├── __init__.py
│   │   ├── shell_type.py       # SINGLE_SHELL, MULTI_SHELL
│   │   ├── distortion.py       # RPE_PAIR, FIELDMAP, NONE
│   │   └── species.py          # HUMAN, NHP
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── bids_validator.py   # BIDS structure validation
│   │   └── config_validator.py # Config validation
│   └── exceptions/
│       ├── __init__.py
│       └── errors.py           # Custom exceptions
│
├── application/                # Application layer
│   ├── __init__.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py             # ProcessingStrategy ABC
│   │   ├── single_shell.py     # SingleShellStrategy
│   │   └── multi_shell.py      # MultiShellStrategy
│   ├── factories/
│   │   ├── __init__.py
│   │   ├── workflow_factory.py # Creates workflows
│   │   └── strategy_factory.py # Creates strategies
│   ├── builders/
│   │   ├── __init__.py
│   │   ├── workflow_builder.py # Builds Nipype workflows
│   │   └── workflow_director.py # Directs construction
│   └── executors/
│       ├── __init__.py
│       └── pipeline_executor.py # Executes workflows
│
├── infrastructure/             # Infrastructure layer
│   ├── __init__.py
│   ├── bids/
│   │   ├── __init__.py
│   │   ├── reader.py           # Reads BIDS datasets
│   │   └── metadata.py         # Extracts metadata
│   ├── freesurfer/
│   │   ├── __init__.py
│   │   └── parcellation.py     # FreeSurfer integration
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── mrtrix/             # MRtrix3 Nipype interfaces
│   │   │   ├── __init__.py
│   │   │   ├── mrconvert.py
│   │   │   ├── dwidenoise.py
│   │   │   ├── dwifslpreproc.py
│   │   │   ├── dwi2response.py
│   │   │   ├── dwi2fod.py
│   │   │   ├── tckgen.py
│   │   │   └── tck2connectome.py
│   │   ├── fsl/                # FSL Nipype interfaces
│   │   │   ├── __init__.py
│   │   │   ├── flirt.py
│   │   │   └── bet.py
│   │   └── ants/               # ANTs Nipype interfaces
│   │       ├── __init__.py
│   │       └── registration.py
│   └── reporting/
│       ├── __init__.py
│       ├── qc_generator.py     # QC report generation
│       └── html_renderer.py    # HTML report rendering
│
└── utils/                      # Utilities
    ├── __init__.py
    ├── paths.py                # Path utilities
    ├── logging.py              # Logging configuration
    └── constants.py            # Global constants
```

### Module Dependencies

```
CLI → Application → Domain
              ↓
       Infrastructure

Legend:
→ = Depends on
```

**Key Principle:** Dependencies flow inward. Domain has no dependencies. Infrastructure depends on domain but not application.

---

## Workflow Design

See `workflow_graph.puml` for visual diagram.

### Nipype Workflow Structure

The Nipype workflow is constructed programmatically based on:
1. Shell configuration (single/multi)
2. Distortion correction strategy (rpe_pair/fieldmap/none)
3. Available data (FreeSurfer, fieldmaps, etc.)

### Example: Single-Shell Workflow

```python
from nipype import Workflow, Node
from nipype.interfaces.mrtrix3 import *

# Created by WorkflowBuilder
wf = Workflow(name='single_shell_dwi')

# Preprocessing
mrconvert = Node(MRConvert(), name='mrconvert')
denoise = Node(DWIDenoise(), name='denoise')
degibbs = Node(MRDeGibbs(), name='degibbs')  # Single-shell only
preproc = Node(DWIFslPreproc(), name='preproc')
biascorrect = Node(DWIBiasCorrect(), name='biascorrect')
mask = Node(DWI2Mask(), name='mask')

# Connect nodes
wf.connect([
    (mrconvert, denoise, [('out_file', 'in_file')]),
    (denoise, degibbs, [('out_file', 'in_file')]),
    (degibbs, preproc, [('out_file', 'in_file')]),
    (preproc, biascorrect, [('out_file', 'in_file')]),
    (biascorrect, mask, [('out_file', 'in_file')])
])

# Response estimation (single-shell uses tournier)
response = Node(ResponseSD(algorithm='tournier'), name='response')
wf.connect([(biascorrect, response, [('out_file', 'in_file')]),
            (mask, response, [('out_file', 'in_mask')])])

# FOD estimation (single-shell uses CSD, not MSMT-CSD)
fod = Node(EstimateFOD(algorithm='csd'), name='fod')
wf.connect([(biascorrect, fod, [('out_file', 'in_file')]),
            (response, fod, [('wm_file', 'wm_txt')]),
            (mask, fod, [('out_file', 'mask_file')])])

# ... tractography, connectomes, etc.
```

### Conditional Node Inclusion

```python
class WorkflowBuilder:
    def add_preprocessing(self):
        # Always included
        self.add_node('mrconvert', MRConvert())
        self.add_node('denoise', DWIDenoise())
        
        # Conditional: only for single-shell
        if self.strategy.should_apply_degibbs():
            self.add_node('degibbs', MRDeGibbs())
        
        # Conditional: depends on distortion correction
        if self.layout.distortion_correction == 'rpe_pair':
            self.add_node('preproc', DWIFslPreproc(rpe_option='rpe_pair'))
        elif self.layout.distortion_correction == 'fieldmap':
            self.add_node('preproc', DWIFslPreproc(rpe_option='rpe_none'))
            # Add fieldmap preprocessing nodes
        else:
            self.add_node('preproc', DWIFslPreproc(rpe_option='rpe_none'))
```

### Workflow Caching

Nipype automatically caches node outputs. If a node's inputs haven't changed, it reuses previous outputs.

```python
# Nipype handles this automatically
workflow.run(plugin='MultiProc', plugin_args={'n_procs': 8})

# On re-run, only changed nodes execute
workflow.run()  # Much faster!
```

---

## Container Strategy

See `deployment_diagram.puml` for visual diagram.

### Dockerfile Structure

```dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip \
    build-essential git curl

# Install MRtrix3
RUN git clone https://github.com/MRtrix3/mrtrix3.git /opt/mrtrix3 && \
    cd /opt/mrtrix3 && \
    ./configure && \
    ./build

# Install FSL
RUN curl -O https://fsl.fmrib.ox.ac.uk/fsldownloads/fslinstaller.py && \
    python3 fslinstaller.py -d /opt/fsl

# Install ANTs
RUN git clone https://github.com/ANTsX/ANTs.git /opt/ants-src && \
    mkdir /opt/ants-build && cd /opt/ants-build && \
    cmake /opt/ants-src && make -j8 && \
    cd ANTS-build && make install

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

# Copy application code
COPY dwi_pipeline/ /app/dwi_pipeline/
WORKDIR /app

# Set up environment
ENV PATH="/opt/mrtrix3/bin:/opt/fsl/bin:/opt/ants/bin:$PATH"
ENV FSLDIR="/opt/fsl"
ENV FREESURFER_HOME="/opt/freesurfer"

# Entry point
ENTRYPOINT ["python3", "-m", "dwi_pipeline"]
```

### Container Usage

```bash
# Basic usage
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01

# With custom config
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  -v $(pwd)/config.json:/config.json:ro \
  dwi-pipeline:latest \
  sub-01 ses-01 --config /config.json

# Singularity equivalent
singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/derivatives/dwi:/out \
  dwi-pipeline.sif \
  sub-01 ses-01
```

### SLURM Integration (Optional)

Users can still use SLURM to orchestrate container execution:

```bash
#!/bin/bash
#SBATCH --array=1-100
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G

subjects=(sub-01 sub-02 ... sub-100)
subject=${subjects[$SLURM_ARRAY_TASK_ID]}

singularity run \
  -B /data/bids:/data:ro \
  -B /data/freesurfer:/freesurfer:ro \
  -B /data/derivatives:/out \
  dwi-pipeline.sif \
  $subject ses-01 --n-threads 8
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Set up project structure and domain models

- [ ] Set up repository with package structure
- [ ] Create domain models (BidsLayout, DwiData, ProcessingConfig)
- [ ] Create enums (ShellType, DistortionStrategy, Species)
- [ ] Implement validation rules
- [ ] Write unit tests for domain layer

**Deliverable:** Domain layer with 100% test coverage

### Phase 2: Infrastructure (Weeks 3-4)

**Goal:** Implement tool interfaces and BIDS reading

- [ ] Create Nipype interfaces for MRtrix3 commands
- [ ] Create Nipype interfaces for FSL commands
- [ ] Create Nipype interfaces for ANTs commands
- [ ] Implement BidsReader
- [ ] Implement FreeSurfer integration
- [ ] Write integration tests with mock data

**Deliverable:** Infrastructure layer with integration tests

### Phase 3: Application Logic (Weeks 5-6)

**Goal:** Implement workflow construction

- [ ] Implement ProcessingStrategy interface
- [ ] Implement SingleShellStrategy
- [ ] Implement MultiShellStrategy
- [ ] Implement WorkflowBuilder
- [ ] Implement WorkflowFactory
- [ ] Write unit tests with mocked strategies

**Deliverable:** Application layer with unit tests

### Phase 4: Workflow Integration (Weeks 7-8)

**Goal:** Build complete Nipype workflows

- [ ] Implement full preprocessing workflow
- [ ] Implement response estimation workflow
- [ ] Implement FOD estimation workflow
- [ ] Implement tractography workflow
- [ ] Implement connectome generation workflow
- [ ] Test workflows with sample data

**Deliverable:** Working end-to-end workflows

### Phase 5: CLI and Execution (Week 9)

**Goal:** Implement command-line interface

- [ ] Implement ArgumentParser
- [ ] Implement ConfigLoader
- [ ] Implement PipelineExecutor
- [ ] Add logging and progress reporting
- [ ] Write CLI tests

**Deliverable:** Functional CLI interface

### Phase 6: Containerization (Week 10)

**Goal:** Build Docker and Singularity images

- [ ] Create Dockerfile
- [ ] Create Singularity recipe
- [ ] Test container builds
- [ ] Optimize image size
- [ ] Document container usage

**Deliverable:** Container images on Docker Hub / Singularity Hub

### Phase 7: Reporting (Week 11)

**Goal:** Implement QC report generation

- [ ] Design HTML report template
- [ ] Implement QC metrics calculation
- [ ] Implement report generation
- [ ] Test report generation

**Deliverable:** QC report generation

### Phase 8: Testing & Documentation (Week 12)

**Goal:** Comprehensive testing and documentation

- [ ] Run full pipeline on test dataset
- [ ] Validate against old pipeline outputs
- [ ] Write comprehensive README
- [ ] Write API documentation
- [ ] Create usage examples

**Deliverable:** Production-ready pipeline

---

## Testing Strategy

### Unit Tests (Domain & Application Layers)

Test business logic without external dependencies:

```python
def test_shell_detection_single_shell():
    bvals = np.array([0, 0, 1000, 1000, 1000])
    dwi_data = DwiData(bvals=bvals, ...)
    assert dwi_data.detect_shells() == ShellType.SINGLE_SHELL

def test_strategy_selection():
    layout = BidsLayout(shell_config='single_shell')
    factory = StrategyFactory()
    strategy = factory.create_strategy(layout)
    assert isinstance(strategy, SingleShellStrategy)
```

### Integration Tests (Infrastructure Layer)

Test tool interfaces with real commands:

```python
@pytest.mark.integration
def test_mrconvert_interface():
    node = MRConvertNode()
    result = node.run(in_file='test.nii.gz', out_file='test.mif')
    assert os.path.exists('test.mif')
```

### End-to-End Tests

Test complete pipeline with sample datasets:

```python
@pytest.mark.slow
def test_full_pipeline_single_shell():
    executor = PipelineExecutor()
    result = executor.run(
        bids_dir='tests/data/bids',
        subject='sub-test01',
        session='ses-01'
    )
    assert result.success
    assert os.path.exists(result.connectome_path)
```

### Test Data

- **Minimal BIDS dataset** - Small synthetic dataset for quick tests
- **Full test dataset** - Real data (anonymized) for validation
- **Expected outputs** - Baseline outputs from current pipeline

---

## Migration Strategy

### Backward Compatibility

1. **Output Format**
   - Maintain same BIDS derivatives structure
   - Keep same connectome CSV format
   - Preserve provenance information

2. **Configuration**
   - Support old config.json format
   - Translate old parameters to new system

3. **Validation**
   - Compare outputs with old pipeline
   - Ensure numerical equivalence (within tolerance)

### Migration Path

1. **Phase 1:** Run both pipelines in parallel
2. **Phase 2:** Validate outputs are equivalent
3. **Phase 3:** Switch to new pipeline
4. **Phase 4:** Deprecate old pipeline

---

## Questions for Discussion

1. **FreeSurfer Requirement**
   - Should FreeSurfer be required or optional?
   - Current plan: Optional, graceful degradation to template-only

2. **Configuration Strategy**
   - CLI flags only or config file support?
   - Current plan: Both, with CLI overriding config file

3. **Parallel Execution**
   - Should container handle multi-threading internally?
   - Current plan: Yes, via Nipype's MultiProc plugin

4. **Output Organization**
   - Strict BIDS derivatives or flexible?
   - Current plan: Strict BIDS compliance

5. **Atlas Management**
   - Ship atlases in container or mount externally?
   - Current plan: Common atlases in container, custom via mount

6. **Provenance**
   - Level of detail in provenance tracking?
   - Current plan: Full Nipype provenance + JSON summary

---

## Next Steps

1. **Review** these diagrams and documentation
2. **Discuss** any concerns or alternative approaches
3. **Prioritize** features and scope
4. **Begin** Phase 1 implementation

---

## References

- [Nipype Documentation](https://nipype.readthedocs.io/)
- [BIDS Specification](https://bids-specification.readthedocs.io/)
- [MRtrix3 Documentation](https://mrtrix.readthedocs.io/)
- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Design Patterns (Gang of Four)](https://en.wikipedia.org/wiki/Design_Patterns)
