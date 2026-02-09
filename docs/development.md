# Development Guide

## Code Structure

The DWI Pipeline follows a clean architecture pattern with four distinct layers:

```
dwi_pipeline/
├── cli/                    # Command-line interface
│   ├── argument_parser.py  # Argument parsing
│   └── config_loader.py    # Configuration loading
├── domain/                 # Core business logic
│   ├── models/             # Data models
│   ├── enums/              # Enumerations
│   ├── exceptions/         # Custom exceptions
│   └── validation/         # Input validation
├── application/            # Business logic orchestration
│   ├── factories/          # Object creation patterns
│   ├── strategies/         # Processing strategies
│   └── builders/           # Workflow construction
├── infrastructure/         # External tool interfaces
│   ├── bids/               # BIDS data handling
│   ├── freesurfer/         # FreeSurfer integration
│   ├── interfaces/         # Nipype wrappers
│   └── reporting/          # QC report generation
└── utils/                  # Utility functions
```

## Key Classes and Interfaces

### Domain Layer

#### BidsLayout (domain/models/bids_layout.py)
Represents the discovered BIDS file structure for a subject/session.

#### DwiData (domain/models/dwi_data.py)
Encapsulates extracted DWI metadata with automatic shell type detection.

#### ProcessingConfig (domain/models/processing_config.py)
Consolidates all processing parameters and derived properties.

#### ProcessingStrategy (application/strategies/base.py)
Abstract base class for processing strategies defining the interface.

### Application Layer

#### StrategyFactory (application/factories/strategy_factory.py)
Factory for creating the appropriate processing strategy based on data characteristics.

#### WorkflowBuilder (application/builders/workflow_builder.py)
Implements the Builder pattern to construct complex Nipype workflows step-by-step.

#### WorkflowDirector (application/builders/workflow_builder.py)
Directs the construction of the workflow using a builder.

### Infrastructure Layer

#### BidsReader (infrastructure/bids/reader.py)
Discovers and validates BIDS dataset structure.

#### BidsMetadataExtractor (infrastructure/bids/metadata.py)
Extracts metadata from BIDS JSON sidecars.

#### FreeSurferValidator (infrastructure/freesurfer/parcellation.py)
Validates FreeSurfer derivative availability.

#### Nipype Interfaces (infrastructure/interfaces/*)
Wrappers for MRtrix3, FSL, and ANTs commands.

## Extension Points

### Adding New Strategies

To add support for a new species or processing approach:

1. Create a new strategy class inheriting from `ProcessingStrategy`
2. Implement the required methods:
   - `create_response_nodes()`
   - `create_fod_nodes()`
   - `should_apply_degibbs()`
   - `get_fod_cutoff()`
3. Register the strategy in `StrategyFactory`

Example for a new NHP single-shell strategy:
```python
# application/strategies/nhp_single_shell.py
from .base import ProcessingStrategy
from ...infrastructure.interfaces.mrtrix import DWI2Response, DWI2FOD

class NhpSingleShellStrategy(ProcessingStrategy):
    def create_response_nodes(self):
        # Use NHP-specific response estimation
        response_node = Node(
            DWI2Response(
                algorithm="tournier",
                out_file="response.txt"
            ),
            name="dwi2response_tournier"
        )
        return [response_node]

    def create_fod_nodes(self):
        # Use NHP-specific FOD estimation
        fod_node = Node(
            DWI2FOD(
                algorithm="csd",
                out_file="fod.mif"
            ),
            name="dwi2fod_csd"
        )
        return [fod_node]

    def should_apply_degibbs(self) -> bool:
        # Different decision logic for NHP
        return False

    def get_fod_cutoff(self) -> float:
        # Different cutoff for NHP
        return 0.05
```

Register in StrategyFactory:
```python
# application/factories/strategy_factory.py
self._strategies: Dict[tuple[Species, ShellType], Type[ProcessingStrategy]] = {
    (Species.HUMAN, ShellType.SINGLE_SHELL): SingleShellStrategy,
    (Species.HUMAN, ShellType.MULTI_SHELL): MultiShellStrategy,
    (Species.NHP, ShellType.SINGLE_SHELL): NhpSingleShellStrategy,  # New registration
}
```

### Custom Nipype Interfaces

To add support for new MRtrix3, FSL, or ANTs commands:

1. Create a new interface class inheriting from `CommandLine`
2. Define inputs and outputs using traits
3. Implement any custom logic in `_list_outputs()` if needed

Example for a new MRtrix3 command:
```python
# infrastructure/interfaces/mrtrix/new_command.py
from nipype.interfaces.base import CommandLine, CommandLineInputSpec, TraitedSpec, File
from nipype.interfaces.base import traits

class NewCommandInputSpec(CommandLineInputSpec):
    in_file = File(
        exists=True,
        desc="Input file",
        mandatory=True,
        position=0,
        argstr="%s"
    )
    out_file = File(
        desc="Output file",
        genfile=True,
        position=1,
        argstr="%s"
    )
    parameter = traits.Float(
        desc="Some parameter",
        argstr="-parameter %f"
    )

class NewCommandOutputSpec(TraitedSpec):
    out_file = File(desc="Output file", exists=True)

class NewCommand(CommandLine):
    _cmd = "new_command"
    input_spec = NewCommandInputSpec
    output_spec = NewCommandOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = self._gen_filename("out_file")
        return outputs

    def _gen_filename(self, name):
        if name == "out_file":
            return self._outputs().out_file or "output.nii.gz"
        return None
```

### New Atlas Support

To add support for new atlases:

1. Add atlas files to the container build
2. Update the parcellation pipeline in `WorkflowBuilder._add_parcellation_pipeline()`
3. Modify constants in `utils/constants.py` if needed

## Testing

### Unit Testing Approach

Unit tests focus on isolated components, particularly domain models and pure functions:

```bash
# Run all unit tests
pytest tests/unit/

# Run specific test files
pytest tests/unit/domain/test_models.py
pytest tests/unit/domain/test_enums.py

# Run specific tests
pytest tests/unit/domain/test_models.py::test_shell_detection
```

### Integration Testing

Integration tests verify the interaction between components:

```bash
# Run integration tests
pytest tests/integration/

# Test workflow construction
pytest tests/integration/test_workflow_builder.py
```

### Test Structure

Tests are organized by layer:

```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_models.py
│   │   ├── test_enums.py
│   │   └── test_validation.py
│   ├── application/
│   │   ├── test_strategies.py
│   │   └── test_factories.py
│   └── infrastructure/
│       └── test_utils.py
├── integration/
│   ├── test_workflow_builder.py
│   └── test_pipeline_execution.py
└── fixtures/
    └── sample_data.py
```

## Development Workflow

### Setting Up Development Environment

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run tests to verify setup:
   ```bash
   pytest tests/
   ```

### Making Changes

1. Create a feature branch
2. Make changes following the established patterns
3. Add tests for new functionality
4. Run the full test suite:
   ```bash
   pytest tests/
   ```
5. Submit a pull request

### Code Style

Follow PEP 8 guidelines and use type hints throughout the codebase. Run linting with:
```bash
flake8 dwi_pipeline/
mypy dwi_pipeline/
```

## Debugging

### Logging

The pipeline uses Python's logging module with configurable verbosity:

```bash
# Enable INFO level logging
python -m dwi_pipeline sub-01 ses-01 -v

# Enable DEBUG level logging
python -m dwi_pipeline sub-01 ses-01 -vv
```

### Nipype Debugging

For workflow debugging, you can inspect the generated Nipype workflow:

```python
# In __main__.py, before workflow.run()
workflow.write_graph(graph2use='colored', format='png', simple_form=False)
```

This generates a visual representation of the workflow graph.