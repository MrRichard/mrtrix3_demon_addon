from typing import List, Tuple

from ..models.processing_config import ProcessingConfig
from ..exceptions.errors import ConfigurationError

class ConfigValidator:
    """
    Validates the integrity and consistency of ProcessingConfig parameters.
    """
    def validate(self, config: ProcessingConfig) -> Tuple[bool, List[str]]:
        """
        Performs validation checks on the provided ProcessingConfig object.

        Args:
            config (ProcessingConfig): The configuration object to validate.

        Returns:
            Tuple[bool, List[str]]: A tuple where the first element is True if
                                     validation passes, False otherwise. The second
                                     element is a list of error messages.
        """
        errors: List[str] = []

        # Validate n_threads
        if not (1 <= config.n_threads <= 32): # Max threads recommended in docs is 32
            errors.append(f"Invalid number of threads specified: {config.n_threads}. Must be between 1 and 32.")

        # Validate output_dir and work_dir are absolute paths
        if not config.output_dir.is_absolute():
            errors.append(f"Output directory must be an absolute path: {config.output_dir}")
        if not config.work_dir.is_absolute():
            errors.append(f"Working directory must be an absolute path: {config.work_dir}")
            
        # Ensure output_dir and work_dir are not the same if rerun is True (to prevent accidental data loss)
        if config.rerun and config.output_dir == config.work_dir:
            errors.append("Output directory and working directory cannot be the same when --rerun is enabled. This is to prevent accidental data loss.")

        # Other potential checks could go here:
        # - existence/writability of output/work dirs (but these are container mounts, so less critical to check here)
        # - species compatibility with other settings (e.g., NHP and specific atlases)

        if not errors:
            return True, []
        else:
            return False, errors
