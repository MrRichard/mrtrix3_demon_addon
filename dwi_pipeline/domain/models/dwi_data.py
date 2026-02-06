from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..enums.shell_type import ShellType

@dataclass
class DwiData:
    """
    Represents the extracted and derived data from a DWI dataset.

    This dataclass holds raw b-values/vectors, along with derived properties
    like shell configuration, phase encoding direction, and total readout time.
    """
    bvals: np.ndarray = field(metadata={"help": "Array of b-values."})
    bvecs: np.ndarray = field(metadata={"help": "Array of b-vectors."})
    pe_direction: str = field(metadata={"help": "Phase encoding direction (e.g., 'j', 'i-')."})
    total_readout_time: float = field(metadata={"help": "Total readout time in seconds."})
    
    # Optional fieldmap-related parameters
    delta_te: Optional[float] = field(default=None, metadata={"help": "Echo time difference for fieldmap correction (in seconds)."})

    # Derived properties
    shell_type: ShellType = field(init=False)
    unique_shells: List[float] = field(init=False)

    def __post_init__(self):
        self._detect_shells()

    def _detect_shells(self) -> None:
        """
        Detects single-shell vs multi-shell from b-value array.
        Populates `shell_type` and `unique_shells`.
        
        A b-value is considered non-zero if greater than 50.
        """
        # Exclude b=0 values (typically b < 50)
        non_zero_bvals = self.bvals[self.bvals > 50]
        
        # Round to nearest 50 for robust comparison, then find unique values
        unique_bvals_rounded = np.unique(np.round(non_zero_bvals / 50) * 50).tolist()
        
        self.unique_shells = sorted(unique_bvals_rounded)
        
        if len(self.unique_shells) == 1:
            self.shell_type = ShellType.SINGLE_SHELL
        elif len(self.unique_shells) > 1:
            self.shell_type = ShellType.MULTI_SHELL
        else:
            # Case where only b=0 is present or no non-zero b-values > 50
            self.shell_type = ShellType.SINGLE_SHELL # Default to single-shell if only b=0
