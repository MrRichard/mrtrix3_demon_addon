from enum import Enum

class DistortionStrategy(Enum):
    """
    Enum for distortion correction strategies.
    """
    RPE_PAIR = "rpe_pair"       # Reverse Phase Encoding pair
    FIELDMAP = "fieldmap"       # Fieldmap (e.g., magnitude and phase)
    NONE = "none"               # No distortion correction possible
