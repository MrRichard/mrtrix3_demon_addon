from typing import List, Tuple
from pathlib import Path

from ..models.bids_layout import BidsLayout
from ..exceptions.errors import BidsValidationError

class BidsValidator:
    """
    Validates the BIDS structure and the existence of critical files
    as represented by a BidsLayout object.
    """
    def validate(self, layout: BidsLayout) -> Tuple[bool, List[str]]:
        """
        Performs comprehensive validation of the BIDSLayout paths.

        Args:
            layout (BidsLayout): The BidsLayout object to validate.

        Returns:
            Tuple[bool, List[str]]: A tuple where the first element is True if
                                     validation passes, False otherwise. The second
                                     element is a list of error messages.
        """
        all_errors: List[str] = []

        # 1. Validate existence of all paths in the layout
        paths_exist, path_errors = layout.validate_paths()
        if not paths_exist:
            all_errors.extend(path_errors)

        # 2. Basic structural checks (e.g., FreeSurfer directory contents)
        #    More detailed FreeSurfer validation is handled by FreeSurferValidator
        #    Here we only check if the freesurfer_dir exists. Detailed validation will be handled externally.
        if not layout.freesurfer_dir.exists() or not layout.freesurfer_dir.is_dir():
            all_errors.append(f"FreeSurfer directory not found or is not a directory: {layout.freesurfer_dir}")

        if not all_errors:
            return True, []
        else:
            return False, all_errors
