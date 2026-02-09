# Architecture Documentation

## System Overview

The DWI Pipeline follows a clean architecture pattern with four distinct layers:

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

## Layered Architecture

### CLI Layer (cli/)
Handles command-line argument parsing and initial validation orchestration.

Key components:
- `argument_parser.py`: Defines and parses command-line arguments
- `config_loader.py`: Loads configuration from command-line arguments

### Application Layer (application/)
Contains business logic for workflow orchestration using the Strategy pattern.

Key components:
- `factories/`: StrategyFactory for selecting processing strategies
- `strategies/`: Concrete strategy implementations (SingleShell, MultiShell)
- `builders/`: WorkflowBuilder for constructing Nipype workflows

### Domain Layer (domain/)
Pure business logic with no external dependencies.

Key components:
- `models/`: Core data structures (BidsLayout, DwiData, ProcessingConfig)
- `enums/`: Enumeration types (Species, ShellType, DistortionStrategy)
- `exceptions/`: Custom exception hierarchy
- `validation/`: Input validation logic

### Infrastructure Layer (infrastructure/)
Wrappers for external tools and interfaces.

Key components:
- `bids/`: BIDS dataset reading and metadata extraction
- `freesurfer/`: FreeSurfer data validation and parcellation handling
- `interfaces/`: Nipype CommandLine wrappers for MRtrix3, FSL, and ANTs
- `reporting/`: Quality control report generation (stub)

## Domain Models

### BidsLayout
Represents the discovered BIDS file structure for a subject/session:
- DWI file paths (AP/PA directions)
- T1-weighted image paths
- FreeSurfer directory paths
- Derived shell configuration and distortion correction strategy

### DwiData
Encapsulates extracted DWI metadata:
- B-values array for shell detection
- Phase encoding direction
- Total readout time
- Automatically detected shell type (SINGLE_SHELL or MULTI_SHELL)

### ProcessingConfig
Consolidates all processing parameters:
- Subject and session identifiers
- Directory paths (BIDS, FreeSurfer, output, work)
- Processing parameters (thread count, species)
- Derived properties (run ID, output directories)

## Strategy Pattern

The pipeline uses a multi-dimensional strategy pattern keyed on (Species, ShellType):

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

Each strategy defines:
- Response function estimation method
- Fiber Orientation Distribution estimation method
- Whether to apply Gibbs ringing removal
- FOD amplitude cutoff for tractography

## Workflow Construction

Workflows are built using the Builder pattern through these steps:

1. **Preprocessing**: mrconvert → dwidenoise → [mrdegibbs] → dwifslpreproc → dwibiascorrect → dwi2mask
2. **Response Estimation**: Algorithm-specific response function estimation
3. **FOD Estimation**: Constrained spherical deconvolution with strategy-specific parameters
4. **Normalization**: mtnormalise for intensity normalization
5. **Tractography**: Registration, 5TT generation, tckgen, tcksift2
6. **Connectome Generation**: Atlas registration and tck2connectome

The WorkflowBuilder handles conditional node inclusion based on:
- Shell type (single vs multi)
- Distortion correction strategy (RPE_PAIR, FIELDMAP, NONE)
- Available FreeSurfer atlases (Desikan-Killiany, Destrieux)