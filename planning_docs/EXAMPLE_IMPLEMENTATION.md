# Example Implementation: WorkflowBuilder

This file demonstrates the proposed code structure, style, and patterns with a concrete implementation example.

## Example: workflow_builder.py

```python
"""
Workflow Builder for constructing Nipype DWI processing workflows.

This module implements the Builder pattern to construct complex Nipype workflows
in a step-by-step manner, allowing for flexible composition and conditional
node inclusion based on data characteristics.

Example:
    >>> from dwi_pipeline.application.strategies import SingleShellStrategy
    >>> from dwi_pipeline.domain.models import ProcessingConfig, BidsLayout
    >>> 
    >>> strategy = SingleShellStrategy()
    >>> config = ProcessingConfig(subject='sub-01', ...)
    >>> layout = BidsLayout(...)
    >>> 
    >>> builder = WorkflowBuilder(strategy, config, layout)
    >>> workflow = (builder
    ...     .add_preprocessing()
    ...     .add_response_estimation()
    ...     .add_fod_estimation()
    ...     .add_tractography()
    ...     .build())
    >>> 
    >>> workflow.run(plugin='MultiProc', plugin_args={'n_procs': 8})
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from nipype import Workflow, Node
from nipype.interfaces import utility as niu

from dwi_pipeline.domain.models import ProcessingConfig, BidsLayout
from dwi_pipeline.domain.enums import DistortionStrategy
from dwi_pipeline.application.strategies import ProcessingStrategy
from dwi_pipeline.infrastructure.interfaces.mrtrix import (
    MRConvert, DWIDenoise, MRDeGibbs, DWIFslPreproc,
    DWIBiasCorrect, DWI2Mask
)

logger = logging.getLogger(__name__)


class WorkflowBuilder:
    """
    Builder for constructing Nipype DWI processing workflows.
    
    This class implements the Builder pattern to construct complex
    Nipype workflows step-by-step. It uses a ProcessingStrategy to
    determine which nodes to include and how to configure them.
    
    Attributes:
        strategy: Processing strategy (single-shell vs multi-shell)
        config: Processing configuration parameters
        layout: BIDS layout with discovered file paths
        workflow: The Nipype workflow being constructed
        nodes: Dictionary of created nodes by name
        
    Example:
        >>> builder = WorkflowBuilder(strategy, config, layout)
        >>> workflow = (builder
        ...     .add_preprocessing()
        ...     .add_fod_estimation()
        ...     .build())
    """
    
    def __init__(
        self,
        strategy: ProcessingStrategy,
        config: ProcessingConfig,
        layout: BidsLayout
    ) -> None:
        """
        Initialize the workflow builder.
        
        Args:
            strategy: Processing strategy to use
            config: Processing configuration
            layout: BIDS layout with input files
        """
        self.strategy = strategy
        self.config = config
        self.layout = layout
        self.workflow: Optional[Workflow] = None
        self.nodes: Dict[str, Node] = {}
        self._reset()
        
    def _reset(self) -> None:
        """Reset the builder state, creating a new empty workflow."""
        workflow_name = f"{self.config.subject}_dwi_pipeline"
        if self.config.session:
            workflow_name = f"{self.config.subject}_{self.config.session}_dwi_pipeline"
            
        self.workflow = Workflow(
            name=workflow_name,
            base_dir=str(self.config.work_dir)
        )
        self.nodes = {}
        logger.info(f"Created new workflow: {workflow_name}")
    
    def add_preprocessing(self) -> WorkflowBuilder:
        """
        Add preprocessing nodes to the workflow.
        
        This includes:
        - Format conversion (mrconvert)
        - Denoising (dwidenoise)
        - Gibbs ringing removal (mrdegibbs, conditional)
        - Distortion correction (dwifslpreproc)
        - Bias field correction (dwibiascorrect)
        - Brain mask generation (dwi2mask)
        
        Returns:
            Self for method chaining
            
        Raises:
            ValueError: If required input files are missing
        """
        logger.info("Adding preprocessing nodes")
        
        # Input specification
        input_node = Node(
            niu.IdentityInterface(fields=['dwi_file', 'bval', 'bvec']),
            name='inputspec'
        )
        input_node.inputs.dwi_file = str(self.layout.dwi_ap)
        input_node.inputs.bval = str(self.layout.dwi_ap_bval)
        input_node.inputs.bvec = str(self.layout.dwi_ap_bvec)
        self.nodes['inputspec'] = input_node
        
        # Convert to MIF format
        mrconvert = Node(
            MRConvert(out_file='dwi.mif'),
            name='mrconvert'
        )
        self.workflow.connect([
            (input_node, mrconvert, [
                ('dwi_file', 'in_file'),
                ('bval', 'in_bval'),
                ('bvec', 'in_bvec')
            ])
        ])
        self.nodes['mrconvert'] = mrconvert
        
        # Denoising
        denoise = Node(
            DWIDenoise(
                out_file='dwi_den.mif',
                noise='noise.mif'
            ),
            name='denoise'
        )
        self.workflow.connect([
            (mrconvert, denoise, [('out_file', 'in_file')])
        ])
        self.nodes['denoise'] = denoise
        
        # Previous node for connection tracking
        prev_node = denoise
        prev_output = 'out_file'
        
        # Conditional: Gibbs ringing removal (single-shell only)
        if self.strategy.should_apply_degibbs():
            logger.info("Adding Gibbs ringing removal (single-shell data)")
            degibbs = Node(
                MRDeGibbs(out_file='dwi_den_degibbs.mif'),
                name='degibbs'
            )
            self.workflow.connect([
                (prev_node, degibbs, [(prev_output, 'in_file')])
            ])
            self.nodes['degibbs'] = degibbs
            prev_node = degibbs
        else:
            logger.info("Skipping Gibbs removal (multi-shell data)")
        
        # Distortion correction
        preproc_node = self._create_distortion_correction_node()
        self.workflow.connect([
            (prev_node, preproc_node, [(prev_output, 'in_file')])
        ])
        self.nodes['dwifslpreproc'] = preproc_node
        
        # Bias field correction
        biascorrect = Node(
            DWIBiasCorrect(
                use_ants=True,
                out_file='dwi_unbiased.mif',
                bias='bias.mif'
            ),
            name='biascorrect'
        )
        self.workflow.connect([
            (preproc_node, biascorrect, [('out_file', 'in_file')])
        ])
        self.nodes['biascorrect'] = biascorrect
        
        # Brain mask generation (unless external mask provided)
        if self.config.external_mask:
            logger.info(f"Using external mask: {self.config.external_mask}")
            mask_input = Node(
                niu.IdentityInterface(fields=['mask_file']),
                name='external_mask'
            )
            mask_input.inputs.mask_file = str(self.config.external_mask)
            self.nodes['mask'] = mask_input
        else:
            logger.info("Generating brain mask with dwi2mask")
            mask = Node(
                DWI2Mask(out_file='mask.mif'),
                name='mask'
            )
            self.workflow.connect([
                (biascorrect, mask, [('out_file', 'in_file')])
            ])
            self.nodes['mask'] = mask
        
        return self
    
    def _create_distortion_correction_node(self) -> Node:
        """
        Create distortion correction node based on available data.
        
        Returns:
            Configured DWIFslPreproc node
            
        Note:
            This method determines the appropriate distortion correction
            strategy based on:
            - Available reverse phase-encode data (rpe_pair)
            - Available fieldmaps (fieldmap correction)
            - Neither available (rpe_none, no correction)
        """
        strategy = self.layout.distortion_correction
        
        if strategy == DistortionStrategy.RPE_PAIR:
            logger.info("Using reverse phase-encode pair distortion correction")
            # Create b0 pair for topup
            # ... (implementation details)
            
            return Node(
                DWIFslPreproc(
                    rpe_option='rpe_pair',
                    pe_dir=self.layout.pe_direction,
                    readout_time=self.layout.total_readout_time,
                    out_file='dwi_preproc.mif'
                ),
                name='dwifslpreproc'
            )
            
        elif strategy == DistortionStrategy.FIELDMAP:
            logger.info("Using fieldmap distortion correction")
            # Prepare fieldmap
            # ... (implementation details)
            
            return Node(
                DWIFslPreproc(
                    rpe_option='rpe_none',
                    pe_dir=self.layout.pe_direction,
                    readout_time=self.layout.total_readout_time,
                    out_file='dwi_preproc.mif'
                    # topup_options with fieldmap
                ),
                name='dwifslpreproc'
            )
            
        else:  # DistortionStrategy.NONE
            logger.warning("No distortion correction - consider acquiring fieldmaps")
            return Node(
                DWIFslPreproc(
                    rpe_option='rpe_none',
                    pe_dir=self.layout.pe_direction,
                    readout_time=self.layout.total_readout_time,
                    out_file='dwi_preproc.mif'
                ),
                name='dwifslpreproc'
            )
    
    def add_response_estimation(self) -> WorkflowBuilder:
        """
        Add response function estimation nodes.
        
        The specific algorithm (tournier vs dhollander) is determined
        by the processing strategy (single-shell vs multi-shell).
        
        Returns:
            Self for method chaining
        """
        logger.info("Adding response function estimation")
        
        response_nodes = self.strategy.create_response_nodes()
        
        for node in response_nodes:
            self.nodes[node.name] = node
            self.workflow.add_nodes([node])
            
            # Connect to preprocessed data and mask
            self.workflow.connect([
                (self.nodes['biascorrect'], node, [('out_file', 'in_file')]),
                (self.nodes['mask'], node, [('out_file', 'in_mask')])
            ])
        
        return self
    
    def add_fod_estimation(self) -> WorkflowBuilder:
        """
        Add fiber orientation distribution (FOD) estimation nodes.
        
        The specific algorithm (CSD vs MSMT-CSD) is determined by
        the processing strategy.
        
        Returns:
            Self for method chaining
        """
        logger.info("Adding FOD estimation")
        
        fod_nodes = self.strategy.create_fod_nodes()
        
        for node in fod_nodes:
            self.nodes[node.name] = node
            self.workflow.add_nodes([node])
            
            # Connect to preprocessed data, mask, and response
            # (connections depend on strategy)
        
        # Intensity normalization
        normalize_nodes = self.strategy.create_normalization_nodes()
        
        for node in normalize_nodes:
            self.nodes[node.name] = node
            self.workflow.add_nodes([node])
        
        return self
    
    def add_tractography(self) -> WorkflowBuilder:
        """
        Add tractography generation nodes.
        
        This includes:
        - Anatomical registration
        - 5-tissue-type segmentation
        - GM-WM interface generation
        - Streamline generation (10M)
        - SIFT filtering (1M)
        
        Returns:
            Self for method chaining
        """
        logger.info("Adding tractography nodes")
        
        # Anatomical registration
        # 5TT generation
        # Tractography
        # SIFT
        # ... (implementation details)
        
        return self
    
    def add_connectome_generation(self) -> WorkflowBuilder:
        """
        Add connectome generation nodes.
        
        This includes:
        - Template registration
        - Atlas transformation to native space
        - Connectome generation for each atlas
        
        Returns:
            Self for method chaining
        """
        logger.info("Adding connectome generation nodes")
        
        # Template registration
        # Atlas transformation
        # Connectome generation
        # ... (implementation details)
        
        return self
    
    def build(self) -> Workflow:
        """
        Build and return the complete workflow.
        
        Returns:
            Constructed Nipype workflow
            
        Raises:
            ValueError: If workflow is not properly constructed
        """
        if not self.workflow:
            raise ValueError("Workflow not initialized")
        
        if not self.nodes:
            raise ValueError("No nodes added to workflow")
        
        logger.info(f"Built workflow with {len(self.nodes)} nodes")
        return self.workflow
    
    def visualize(self, output_file: Optional[Path] = None) -> None:
        """
        Generate a visualization of the workflow graph.
        
        Args:
            output_file: Output file path for visualization
                        (defaults to workflow_name.png)
        """
        if output_file is None:
            output_file = Path(f"{self.workflow.name}_graph.png")
        
        self.workflow.write_graph(
            graph2use='flat',
            format='png',
            simple_form=True
        )
        logger.info(f"Workflow visualization saved to {output_file}")


class WorkflowDirector:
    """
    Director for constructing complete workflows.
    
    This class provides high-level methods for constructing
    common workflow configurations. It orchestrates the
    WorkflowBuilder to create complete workflows.
    
    Example:
        >>> director = WorkflowDirector(builder)
        >>> workflow = director.construct_full_pipeline()
    """
    
    def __init__(self, builder: WorkflowBuilder) -> None:
        """
        Initialize the director with a workflow builder.
        
        Args:
            builder: WorkflowBuilder instance
        """
        self.builder = builder
        
    def construct_full_pipeline(self) -> Workflow:
        """
        Construct a complete DWI processing pipeline.
        
        This includes all steps from preprocessing through
        connectome generation.
        
        Returns:
            Complete Nipype workflow
        """
        logger.info("Constructing full DWI processing pipeline")
        
        return (self.builder
            .add_preprocessing()
            .add_response_estimation()
            .add_fod_estimation()
            .add_tractography()
            .add_connectome_generation()
            .build())
    
    def construct_preprocessing_only(self) -> Workflow:
        """
        Construct preprocessing pipeline only.
        
        Useful for testing or for cases where only
        preprocessed data is needed.
        
        Returns:
            Preprocessing-only workflow
        """
        logger.info("Constructing preprocessing-only pipeline")
        
        return (self.builder
            .add_preprocessing()
            .build())
    
    def construct_connectome_only(self) -> Workflow:
        """
        Construct connectome generation pipeline only.
        
        Assumes preprocessing and FOD estimation have already
        been completed.
        
        Returns:
            Connectome-only workflow
        """
        logger.info("Constructing connectome-only pipeline")
        
        return (self.builder
            .add_tractography()
            .add_connectome_generation()
            .build())
```

## Key Implementation Features

### 1. Type Hints

All functions have comprehensive type hints:
- Parameter types
- Return types
- Optional types
- Complex types (List, Dict, etc.)

This enables:
- IDE autocomplete
- Static type checking with mypy
- Better documentation

### 2. Docstrings

Google-style docstrings for all classes and methods:
- Brief description
- Args section
- Returns section
- Raises section
- Examples section

### 3. Logging

Structured logging throughout:
- Info for major steps
- Debug for detailed operations
- Warning for potential issues
- Error for failures

### 4. Error Handling

Explicit error handling:
- Validation of inputs
- Clear error messages
- Custom exceptions

### 5. Method Chaining

Builder pattern with method chaining:
```python
workflow = (builder
    .add_preprocessing()
    .add_fod_estimation()
    .add_tractography()
    .build())
```

### 6. Conditional Logic

Clear conditional node inclusion:
```python
if self.strategy.should_apply_degibbs():
    # Add degibbs node
else:
    # Skip degibbs
```

### 7. Separation of Concerns

- Builder constructs workflows
- Strategy determines algorithms
- Director orchestrates construction
- Each has single responsibility

### 8. Testability

Design enables easy testing:
```python
def test_preprocessing_nodes():
    strategy = MockStrategy()
    config = ProcessingConfig(...)
    layout = BidsLayout(...)
    
    builder = WorkflowBuilder(strategy, config, layout)
    builder.add_preprocessing()
    
    assert 'denoise' in builder.nodes
    assert 'biascorrect' in builder.nodes
```

### 9. Configuration

Flexible configuration via domain models:
```python
config = ProcessingConfig(
    subject='sub-01',
    session='ses-01',
    work_dir=Path('/tmp/work'),
    external_mask=Path('/path/to/mask.nii.gz'),
    rerun=False
)
```

### 10. Documentation

Comprehensive inline documentation:
- Method purposes
- Design decisions
- Edge cases
- Examples

This code structure provides:
- **Readability** - Clear, self-documenting code
- **Maintainability** - Easy to modify and extend
- **Testability** - Each component can be tested independently
- **Reliability** - Type checking and validation
- **Usability** - Clear API with good examples
