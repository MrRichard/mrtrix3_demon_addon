from abc import ABC, abstractmethod
from typing import List
from nipype.pipeline.engine import Node

from ...domain.models.bids_layout import BidsLayout
from ...domain.models.processing_config import ProcessingConfig
from ...domain.models.dwi_data import DwiData

class ProcessingStrategy(ABC):
    """
    Abstract Base Class for DWI processing strategies.
    
    This class defines the interface for different processing strategies,
    such as single-shell vs. multi-shell, or human vs. NHP.
    Each strategy encapsulates the specific algorithms and parameters
    required for its type of data.
    """
    def __init__(self, layout: BidsLayout, config: ProcessingConfig, dwi_data: DwiData):
        self.layout = layout
        self.config = config
        self.dwi_data = dwi_data

    @abstractmethod
    def create_response_nodes(self) -> List[Node]:
        """
        Creates the Nipype nodes for response function estimation.
        
        Returns:
            A list of configured Nipype nodes.
        """
        pass

    @abstractmethod
    def create_fod_nodes(self) -> List[Node]:
        """
        Creates the Nipype nodes for Fiber Orientation Distribution (FOD) estimation.
        
        Returns:
            A list of configured Nipype nodes.
        """
        pass

    @abstractmethod
    def should_apply_degibbs(self) -> bool:
        """
        Determines whether Gibbs ringing removal should be applied.
        
        Returns:
            True if mrdegibbs should be run, False otherwise.
        """
        pass

    @abstractmethod
    def get_fod_cutoff(self) -> float:
        """
        Returns the FOD amplitude cutoff value for tractography.
        
        Returns:
            The cutoff value as a float.
        """
        pass

    def create_preprocessing_nodes(self) -> List[Node]:
        """
        Creates the common preprocessing nodes.
        This can be overridden by subclasses if needed.
        """
        # Default implementation for common steps
        # This will be expanded in the WorkflowBuilder, but the strategy can
        # influence which nodes are created.
        return []

    def create_tractography_nodes(self) -> List[Node]:
        """
        Creates the tractography nodes.
        This can be overridden by subclasses if needed.
        """
        # Default implementation
        return []
