from typing import List
from nipype.pipeline.engine import Node

from .base import ProcessingStrategy
from ...infrastructure.interfaces.mrtrix import DWI2Response, DWI2FOD

class SingleShellStrategy(ProcessingStrategy):
    """
    Concrete processing strategy for single-shell DWI data.
    """
    def create_response_nodes(self) -> List[Node]:
        """
        Creates nodes for single-shell response function estimation using the 'tournier' algorithm.
        """
        response_node = Node(
            DWI2Response(
                algorithm="tournier",
                out_file="response.txt"
            ),
            name="dwi2response_tournier"
        )
        return [response_node]

    def create_fod_nodes(self) -> List[Node]:
        """
        Creates nodes for single-shell FOD estimation using the 'csd' algorithm.
        """
        fod_node = Node(
            DWI2FOD(
                algorithm="csd",
                out_file="fod.mif"
            ),
            name="dwi2fod_csd"
        )
        return [fod_node]

    def should_apply_degibbs(self) -> bool:
        """
        Gibbs ringing removal is recommended for single-shell data.
        """
        return True

    def get_fod_cutoff(self) -> float:
        """
        Returns the FOD amplitude cutoff value for single-shell tractography.
        """
        return 0.1
