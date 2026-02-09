# API Reference

## CLI Layer

### argument_parser.py

#### create_parser()
Creates and configures the argument parser for the CLI.

**Arguments:**
- None

**Returns:**
- `argparse.ArgumentParser`: Configured argument parser

### config_loader.py

*Currently empty - placeholder for configuration loading functionality*

## Domain Layer

### models/bids_layout.py

#### BidsLayout
Dataclass representing the discovered BIDS file structure.

**Attributes:**
- `subject` (str): Subject ID
- `session` (Optional[str]): Session ID
- `dwi_ap` (Path): AP DWI file path
- `dwi_ap_bval` (Path): AP bval file path
- `dwi_ap_bvec` (Path): AP bvec file path
- `dwi_ap_json` (Path): AP JSON file path
- `dwi_pa` (Optional[Path]): PA DWI file path (for RPE_PAIR)
- `dwi_pa_bval` (Optional[Path]): PA bval file path
- `dwi_pa_bvec` (Optional[Path]): PA bvec file path
- `t1w` (Path): T1-weighted image path
- `t1w_json` (Path): T1w JSON file path
- `fs_subject_dir` (Path): FreeSurfer subject directory
- `fs_brain` (Path): FreeSurfer brain.mgz path
- `fs_aparc_aseg` (Path): FreeSurfer aparc+aseg.mgz path
- `fs_aparc_destrieux` (Optional[Path]): FreeSurfer aparc.a2009s+aseg.mgz path
- `shell_config` (Optional[ShellType]): Detected shell configuration
- `distortion_correction` (Optional[DistortionStrategy]): Distortion correction strategy

### models/dwi_data.py

#### DwiData
Dataclass encapsulating extracted DWI metadata.

**Attributes:**
- `bvals` (np.ndarray): Array of b-values
- `pe_direction` (str): Phase encoding direction
- `total_readout_time` (float): Total readout time
- `shell_type` (ShellType): Detected shell type (automatically determined)

#### ShellTypeDetection
Utility functions for shell type detection from b-values.

### models/processing_config.py

#### ProcessingConfig
Dataclass for processing configuration parameters.

**Attributes:**
- `subject` (str): Subject ID
- `output_dir` (Path): Base directory for outputs
- `work_dir` (Path): Working directory for intermediates
- `bids_dir` (Path): Root BIDS directory
- `freesurfer_dir` (Path): FreeSurfer derivatives directory
- `session` (Optional[str]): Session ID
- `n_threads` (int): Number of threads for parallel processing
- `species` (Species): Species of the subject
- `rerun` (bool): Force re-execution flag
- `run_id` (str): Unique identifier for the run (derived)

**Properties:**
- `nipype_work_dir` (Path): Nipype working directory
- `subject_output_dir` (Path): Subject output directory

### enums/species.py

#### Species
Enumeration of supported species.

**Values:**
- `HUMAN`: Human subjects
- `NHP`: Non-human primates (planned)

### enums/shell_type.py

#### ShellType
Enumeration of DWI shell configurations.

**Values:**
- `SINGLE_SHELL`: Single non-zero b-value
- `MULTI_SHELL`: Multiple non-zero b-values

### enums/distortion.py

#### DistortionStrategy
Enumeration of distortion correction strategies.

**Values:**
- `RPE_PAIR`: Reverse phase encode pair
- `FIELDMAP`: Fieldmap-based correction
- `NONE`: No distortion correction

### exceptions/errors.py

#### PipelineError
Base exception for all pipeline-specific errors.

#### BidsValidationError
Raised when BIDS dataset validation fails.

#### FreeSurferError
Raised when FreeSurfer data is missing or invalid.

#### MissingMetadataError
Raised when required metadata is missing.

#### ConfigurationError
Raised when configuration is invalid.

#### WorkflowBuildError
Raised when workflow construction fails.

#### WorkflowExecutionError
Raised when workflow execution fails.

#### ReportGenerationError
Raised when report generation fails.

### validation/bids_validator.py

*Placeholder for BIDS validation functionality*

### validation/config_validator.py

*Placeholder for configuration validation functionality*

## Application Layer

### strategies/base.py

#### ProcessingStrategy
Abstract base class defining the strategy pattern interface.

**Methods:**
- `create_response_nodes()`: Create response estimation nodes
- `create_fod_nodes()`: Create FOD estimation nodes
- `should_apply_degibbs()`: Whether to apply Gibbs ringing removal
- `get_fod_cutoff()`: Get FOD amplitude cutoff value

### strategies/single_shell.py

#### SingleShellStrategy
Concrete strategy for single-shell DWI processing.

**Implementation Details:**
- Uses `dwi2response tournier` for response estimation
- Uses `dwi2fod csd` for FOD estimation
- Applies Gibbs ringing removal
- Uses 0.1 FOD cutoff

### strategies/multi_shell.py

#### MultiShellStrategy
Concrete strategy for multi-shell DWI processing.

**Implementation Details:**
- Uses `dwi2response dhollander` for response estimation
- Uses `dwi2fod msmt_csd` for FOD estimation
- Skips Gibbs ringing removal
- Uses 0.06 FOD cutoff

### factories/strategy_factory.py

#### StrategyFactory
Factory for creating processing strategies.

**Methods:**
- `create_strategy(layout, config, dwi_data)`: Creates appropriate strategy

### factories/workflow_factory.py

#### WorkflowFactory
Factory for creating Nipype workflows.

**Methods:**
- `create_workflow(layout, config, dwi_data)`: Creates workflow with strategy

### builders/workflow_builder.py

#### WorkflowBuilder
Builder for constructing Nipype workflows step-by-step.

**Methods:**
- `add_preprocessing()`: Adds preprocessing nodes
- `add_response_estimation()`: Adds response estimation nodes
- `add_fod_estimation()`: Adds FOD estimation nodes
- `add_normalisation()`: Adds mtnormalise nodes
- `add_tractography()`: Adds tractography and connectome nodes
- `build()`: Returns constructed workflow

#### WorkflowDirector
Director for orchestrating workflow construction.

**Methods:**
- `construct_full_pipeline()`: Constructs complete pipeline

## Infrastructure Layer

### bids/reader.py

#### BidsReader
Reader for discovering BIDS dataset structure.

**Methods:**
- `discover(subject, session)`: Discovers BIDS layout

### bids/metadata.py

#### BidsMetadataExtractor
Extractor for BIDS JSON metadata.

**Methods:**
- `extract_dwi_metadata()`: Extracts DWI metadata
- `determine_distortion_strategy()`: Determines distortion correction strategy

### freesurfer/parcellation.py

#### FreeSurferValidator
Validator for FreeSurfer derivative availability.

**Methods:**
- `validate(subject, session)`: Validates FreeSurfer data

### interfaces/mrtrix/

Collection of Nipype CommandLine wrappers for MRtrix3 commands.

#### MRConvert
Wrapper for `mrconvert` command.

#### DWIDenoise
Wrapper for `dwidenoise` command.

#### MRDeGibbs
Wrapper for `mrdegibbs` command.

#### DWIFslPreproc
Wrapper for `dwifslpreproc` command.

#### DWIBiasCorrect
Wrapper for `dwibiascorrect` command.

#### DWI2Mask
Wrapper for `dwi2mask` command.

#### DWI2Response
Wrapper for `dwi2response` command.

#### DWI2FOD
Wrapper for `dwi2fod` command.

#### DWIExtract
Wrapper for `dwiextract` command.

#### TT5Gen
Wrapper for `5ttgen` command.

#### TT5ToGMWMI
Wrapper for `5tt2gmwmi` command.

#### TCKGen
Wrapper for `tckgen` command.

#### TckSift2
Wrapper for `tcksift2` command.

#### TCK2Connectome
Wrapper for `tck2connectome` command.

#### MtNormalise
Wrapper for `mtnormalise` command.

#### LabelConvert
Wrapper for `labelconvert` command.

### interfaces/fsl/

Collection of Nipype CommandLine wrappers for FSL commands.

#### Flirt
Wrapper for `flirt` command.

#### Bet
Wrapper for `bet` command.

#### FSLPrepareFieldmap
Wrapper for `fsl_prepare_fieldmap` command.

### interfaces/ants/

Collection of Nipype CommandLine wrappers for ANTs commands.

*Currently minimal implementation*

### reporting/

#### qc_generator.py
*Empty stub - placeholder for QC report generation*

#### html_renderer.py
*Empty stub - placeholder for HTML rendering*

## Utilities

### utils/constants.py

Constants and utility functions for path resolution.

#### find_mrtrix_lut_dir()
Locates MRtrix3 LUT directory.

#### find_freesurfer_color_lut()
Locates FreeSurfer color lookup table.

### utils/paths.py

*Empty stub - placeholder for path utilities*

### utils/logging.py

*Empty stub - placeholder for logging utilities*