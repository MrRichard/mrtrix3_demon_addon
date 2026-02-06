class PipelineError(Exception):
    """Base exception for all custom pipeline errors."""
    pass

class BidsValidationError(PipelineError):
    """Exception raised for BIDS validation errors."""
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors

class FreeSurferError(PipelineError):
    """Exception raised for FreeSurfer related errors, especially missing data."""
    pass

class MissingMetadataError(PipelineError):
    """Exception raised when critical BIDS JSON metadata is missing."""
    pass

class ConfigurationError(PipelineError):
    """Exception raised for invalid or inconsistent configuration parameters."""
    pass

class WorkflowBuildError(PipelineError):
    """Exception raised when there's an issue building the Nipype workflow."""
    pass

class WorkflowExecutionError(PipelineError):
    """Exception raised when the Nipype workflow execution fails."""
    pass

class ReportGenerationError(PipelineError):
    """Exception raised when there's an issue generating the QC report."""
    pass
