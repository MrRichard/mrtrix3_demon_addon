from typing import List
from nipype.pipeline.engine import Node

from .base import ProcessingStrategy
from ...infrastructure.interfaces.mrtrix import DWI2Response, DWI2FOD

class MultiShellStrategy(ProcessingStrategy):
    """
    Concrete processing strategy for multi-shell DWI data.
    """
    def create_response_nodes(self) -> List[Node]:
        """
        Creates nodes for multi-shell response function estimation using the 'dhollander' algorithm.
        This separates the response into WM, GM, and CSF.
        """
        response_node = Node(
            DWI2Response(
                algorithm="dhollander",
                wm_file="wm_response.txt",
                gm_file="gm_response.txt",
                csf_file="csf_response.txt"
            ),
            name="dwi2response_dhollander"
        )
        return [response_node]

    def create_fod_nodes(self) -> List[Node]:
        """
        Creates nodes for multi-shell FOD estimation using Multi-Shell Multi-Tissue CSD (msmt_csd).
        """
        fod_node = Node(
            DWI2FOD(
                algorithm="msmt_csd",
                wm_odf="wm_fod.mif",
                gm_odf="gm_fod.mif",
                csf_odf="csf_fod.mif"
            ),
            name="dwi2fod_msmt"
        )
        return [fod_node]

    def should_apply_degibbs(self) -> bool:
        """
        Gibbs ringing removal is not recommended for multi-shell data with MSMT-CSD.
        """
        return False

    def get_fod_cutoff(self) -> float:
        """
        Returns the FOD amplitude cutoff value for multi-shell tractography.
        """
        return 0.06
