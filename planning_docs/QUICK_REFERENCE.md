# MRtrix3 DWI Pipeline - Quick Reference Guide

## Architecture Summary

### Layered Architecture

```
┌─────────────────────────┐
│   Presentation (CLI)    │  ← User interaction
├─────────────────────────┤
│  Application (Logic)    │  ← Orchestration & workflows
├─────────────────────────┤
│   Domain (Models)       │  ← Business logic (pure Python)
├─────────────────────────┤
│ Infrastructure (Tools)  │  ← External dependencies
└─────────────────────────┘

Dependencies flow inward (Dependency Inversion)
Domain has zero external dependencies
```

## Design Patterns Quick Reference

### 1. Strategy Pattern - Processing Algorithms

**When:** Different algorithms for single-shell vs multi-shell

```python
strategy: ProcessingStrategy = SingleShellStrategy()
# OR
strategy: ProcessingStrategy = MultiShellStrategy()

# Both implement same interface
response_nodes = strategy.create_response_nodes()
fod_nodes = strategy.create_fod_nodes()
```

**Files:**
- `application/strategies/base.py` - Abstract interface
- `application/strategies/single_shell.py` - Single-shell implementation
- `application/strategies/multi_shell.py` - Multi-shell implementation

**Decision Criteria:**
```python
if shell_count == 1:
    return SingleShellStrategy()
else:
    return MultiShellStrategy()
```

### 2. Factory Pattern - Workflow Creation

**When:** Creating appropriate workflow based on data

```python
factory = WorkflowFactory()
workflow = factory.create_workflow(layout, config)
```

**Files:**
- `application/factories/workflow_factory.py`

**Decides:**
- Which strategy to use
- Which builder to instantiate
- Which director method to call

### 3. Builder Pattern - Workflow Construction

**When:** Constructing complex Nipype workflows step-by-step

```python
builder = WorkflowBuilder(strategy, config, layout)
workflow = (builder
    .add_preprocessing()
    .add_response_estimation()
    .add_fod_estimation()
    .add_tractography()
    .add_connectome_generation()
    .build())
```

**Files:**
- `application/builders/workflow_builder.py` - Builder
- `application/builders/workflow_director.py` - Director

**Benefits:**
- Fluent interface
- Conditional node inclusion
- Reusable construction logic

### 4. Repository Pattern - Data Access

**When:** Abstracting BIDS data access

```python
repo = BidsRepository()
layout = repo.find_layout(subject, session)
```

**Files:**
- `infrastructure/bids/reader.py`

**Benefits:**
- Testable (mock repository)
- Swappable implementations
- Centralized data access

### 5. Template Method Pattern - Workflow Skeleton

**When:** Common workflow structure with variable steps

```python
class BaseWorkflow:
    def execute(self):
        self.validate()
        self.preprocess()
        self.estimate_response()  # Varies
        self.estimate_fod()       # Varies
        self.tractography()
        self.connectome()
```

## Key Domain Models

### BidsLayout

Represents discovered BIDS data structure:

```python
@dataclass
class BidsLayout:
    subject: str
    session: Optional[str]
    dwi_ap: Path
    dwi_pa: Optional[Path]
    t1w: Path
    freesurfer_dir: Optional[Path]
    distortion_correction: DistortionStrategy
    shell_config: ShellType
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Returns (is_valid, errors)"""
```

### ProcessingConfig

Configuration parameters:

```python
@dataclass
class ProcessingConfig:
    subject: str
    session: Optional[str]
    output_dir: Path
    work_dir: Path
    n_threads: int
    rerun: bool
    external_mask: Optional[Path]
    
    @classmethod
    def from_args(cls, args) -> ProcessingConfig:
        """Create from CLI arguments"""
```

### DwiData

DWI-specific metadata:

```python
@dataclass
class DwiData:
    bvals: np.ndarray
    bvecs: np.ndarray
    shell_type: ShellType
    pe_direction: str
    total_readout_time: float
    
    def detect_shells(self) -> ShellType:
        """Auto-detect single vs multi-shell"""
```

## Enums

### ShellType

```python
class ShellType(Enum):
    SINGLE_SHELL = "single_shell"
    MULTI_SHELL = "multi_shell"
```

### DistortionStrategy

```python
class DistortionStrategy(Enum):
    RPE_PAIR = "rpe_pair"      # Reverse PE acquisition
    FIELDMAP = "fieldmap"       # Magnitude + phase
    NONE = "none"               # No correction
```

### Species

```python
class Species(Enum):
    HUMAN = "human"
    NHP = "nhp"
```

## Workflow Node Conditional Logic

### When to include nodes:

| Node | Condition |
|------|-----------|
| `mrdegibbs` | Single-shell only |
| `dwi2response (tournier)` | Single-shell |
| `dwi2response (dhollander)` | Multi-shell |
| `dwi2fod (csd)` | Single-shell |
| `dwi2fod (msmt_csd)` | Multi-shell |
| `b0_pair creation` | RPE_PAIR distortion |
| `fieldmap prep` | FIELDMAP distortion |
| `FreeSurfer connectomes` | FreeSurfer data available |

### Parameter differences:

| Parameter | Single-Shell | Multi-Shell |
|-----------|--------------|-------------|
| FOD cutoff | 0.1 | 0.06 |
| Response function | tournier | dhollander |
| FOD algorithm | csd | msmt_csd |
| mrdegibbs | Yes | No |
| mtnormalise tissues | 1 (WM only) | 3 (WM+GM+CSF) |

## Container Usage Patterns

### Basic Execution

```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01
```

### With Custom Config

```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  -v $(pwd)/config.json:/config.json:ro \
  dwi-pipeline:latest \
  sub-01 ses-01 --config /config.json
```

### Parallel Processing

```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/freesurfer:/freesurfer:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-01 ses-01 --n-threads 8
```

### NHP Processing

```bash
docker run --rm \
  -v /data/bids:/data:ro \
  -v /data/derivatives/dwi:/out \
  dwi-pipeline:latest \
  sub-NHP01 ses-01 --species nhp
```

## Nipype Workflow Tips

### Creating Nodes

```python
from nipype import Node
from nipype.interfaces.mrtrix3 import DWIDenoise

node = Node(
    DWIDenoise(out_file='dwi_den.mif'),
    name='denoise'
)
```

### Connecting Nodes

```python
workflow.connect([
    (node_a, node_b, [('out_file', 'in_file')]),
    (node_a, node_c, [('out_file', 'in_file')])
])
```

### Conditional Nodes

```python
if condition:
    node = Node(Interface(), name='conditional_node')
    workflow.add_nodes([node])
    workflow.connect([(prev_node, node, [('out', 'in')])])
```

### Running Workflows

```python
# Serial execution
workflow.run()

# Parallel execution
workflow.run(plugin='MultiProc', plugin_args={'n_procs': 8})

# With specific working directory
workflow.base_dir = '/tmp/work'
workflow.run()
```

## Testing Patterns

### Unit Test (Domain)

```python
def test_shell_detection():
    bvals = np.array([0, 0, 1000, 1000])
    dwi = DwiData(bvals=bvals, ...)
    assert dwi.detect_shells() == ShellType.SINGLE_SHELL
```

### Mock Test (Application)

```python
def test_workflow_builder():
    strategy = Mock(ProcessingStrategy)
    strategy.should_apply_degibbs.return_value = True
    
    builder = WorkflowBuilder(strategy, config, layout)
    builder.add_preprocessing()
    
    assert 'degibbs' in builder.nodes
```

### Integration Test (Infrastructure)

```python
@pytest.mark.integration
def test_mrconvert():
    node = MRConvertNode()
    result = node.run(in_file='test.nii.gz')
    assert os.path.exists(result.outputs.out_file)
```

## File Organization Checklist

```
dwi_pipeline/
├── __init__.py               ✓ Package marker
├── __main__.py               ✓ Entry point
├── cli/                      ✓ User interface
├── application/              ✓ Business logic orchestration
│   ├── strategies/           ✓ Processing algorithms
│   ├── factories/            ✓ Object creation
│   ├── builders/             ✓ Workflow construction
│   └── executors/            ✓ Execution logic
├── domain/                   ✓ Pure business logic
│   ├── models/               ✓ Data structures
│   ├── enums/                ✓ Constants
│   ├── validation/           ✓ Rules
│   └── exceptions/           ✓ Errors
└── infrastructure/           ✓ External dependencies
    ├── bids/                 ✓ BIDS I/O
    ├── interfaces/           ✓ Tool wrappers
    │   ├── mrtrix/           ✓ MRtrix3 nodes
    │   ├── fsl/              ✓ FSL nodes
    │   └── ants/             ✓ ANTs nodes
    └── reporting/            ✓ QC reports
```

## Common Mistakes to Avoid

### ❌ Don't: Domain depends on infrastructure

```python
# BAD: Domain importing infrastructure
class BidsLayout:
    def __init__(self):
        from infrastructure.bids import BidsReader  # WRONG
        self.reader = BidsReader()
```

### ✅ Do: Infrastructure depends on domain

```python
# GOOD: Infrastructure imports domain
class BidsReader:
    def read(self) -> BidsLayout:
        from domain.models import BidsLayout
        return BidsLayout(...)
```

### ❌ Don't: Hard-code tool calls

```python
# BAD
def preprocess(self):
    subprocess.run(['dwidenoise', 'in.mif', 'out.mif'])
```

### ✅ Do: Use Nipype interfaces

```python
# GOOD
def preprocess(self):
    node = Node(DWIDenoise(), name='denoise')
    return node
```

### ❌ Don't: Mix concerns

```python
# BAD: Single class doing too much
class Pipeline:
    def __init__(self):
        self.read_bids()
        self.create_workflow()
        self.execute()
        self.generate_report()
```

### ✅ Do: Separate concerns

```python
# GOOD: Each class has one responsibility
reader = BidsReader()
factory = WorkflowFactory()
executor = PipelineExecutor()
reporter = ReportGenerator()

layout = reader.read(...)
workflow = factory.create(...)
results = executor.run(workflow)
reporter.generate(results)
```

## Questions? Checklist

Before implementing, ask:

- [ ] Is this the right layer? (Domain/Application/Infrastructure)
- [ ] Does this class have a single responsibility?
- [ ] Can this be tested without external dependencies?
- [ ] Is this strategy-specific or common?
- [ ] Should this be conditional?
- [ ] Is there an appropriate design pattern?
- [ ] Are dependencies pointing inward?
- [ ] Is this documented?
- [ ] Are types annotated?
- [ ] Is error handling appropriate?

## Next Steps

1. Review PlantUML diagrams
2. Review architecture document
3. Review example implementation
4. Discuss any concerns
5. Begin Phase 1 (Domain layer)
