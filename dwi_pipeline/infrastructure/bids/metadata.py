import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import numpy as np

from ...domain.models.bids_layout import BidsLayout
from ...domain.models.dwi_data import DwiData
from ...domain.enums.distortion import DistortionStrategy
from ...domain.exceptions.errors import MissingMetadataError, BidsValidationError

logger = logging.getLogger(__name__)

class BidsMetadataExtractor:
    """
    Extracts and validates critical metadata from BIDS JSON sidecar files
    and b-value files. Also determines distortion correction strategy.
    """
    def __init__(self, bids_layout: BidsLayout):
        self.bids_layout = bids_layout
        self._dwi_json_content: Optional[Dict[str, Any]] = None
        self._phasediff_json_content: Optional[Dict[str, Any]] = None

    def _load_json(self, json_path: Path) -> Dict[str, Any]:
        """Loads and returns content of a JSON file."""
        if not json_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        with open(json_path, 'r') as f:
            return json.load(f)

    def extract_dwi_metadata(self) -> DwiData:
        """
        Extracts DWI-specific metadata (b-values, b-vectors, PE direction, TRT)
        and creates a DwiData object.
        """
        self._dwi_json_content = self._load_json(self.bids_layout.dwi_ap_json)
        
        bvals = np.loadtxt(self.bids_layout.dwi_ap_bval)
        bvecs = np.loadtxt(self.bids_layout.dwi_ap_bvec)

        if bvals.ndim != 1 or bvecs.ndim != 2 or bvals.shape[0] != bvecs.shape[1]:
            raise BidsValidationError(f"Mismatched dimensions in bval/bvec files for {self.bids_layout.dwi_ap.name}")

        pe_direction = self._get_pe_direction(self._dwi_json_content)
        total_readout_time = self._get_total_readout_time(self._dwi_json_content)
        
        delta_te = None
        if self.bids_layout.phasediff_json:
            self._phasediff_json_content = self._load_json(self.bids_layout.phasediff_json)
            delta_te = self._get_delta_te(self._phasediff_json_content)

        dwi_data = DwiData(
            bvals=bvals,
            bvecs=bvecs,
            pe_direction=pe_direction,
            total_readout_time=total_readout_time,
            delta_te=delta_te
        )
        return dwi_data

    def _get_pe_direction(self, dwi_json: Dict[str, Any]) -> str:
        """Extracts phase encoding direction from DWI JSON."""
        pe_dir_str = dwi_json.get("PhaseEncodingDirection")
        if not pe_dir_str:
            # Try to derive from InPlanePhaseEncodingDirection and acquisition matrix
            # This is a simplification; full BIDS requires more robust derivation
            in_plane_pe = dwi_json.get("InPlanePhaseEncodingDirection")
            if in_plane_pe == "COL": # Column encoding, typically 'i' or 'i-'
                pe_dir_str = "i" # Assuming default positive
            elif in_plane_pe == "ROW": # Row encoding, typically 'j' or 'j-'
                pe_dir_str = "j" # Assuming default positive
            else:
                raise MissingMetadataError(
                    f"Neither 'PhaseEncodingDirection' nor 'InPlanePhaseEncodingDirection' found in {self.bids_layout.dwi_ap_json.name}"
                )
        
        # Validate format
        if pe_dir_str not in ["i", "j", "k", "i-", "j-", "k-"]:
            raise BidsValidationError(f"Invalid 'PhaseEncodingDirection' format: {pe_dir_str}", [f"Invalid PE dir: {pe_dir_str}"])
        
        return pe_dir_str

    def _get_total_readout_time(self, dwi_json: Dict[str, Any]) -> float:
        """Extracts or calculates TotalReadoutTime from DWI JSON."""
        trt = dwi_json.get("TotalReadoutTime")
        if trt is None:
            # Attempt to calculate if EffectiveEchoSpacing and ReconMatrixPE are available
            ees = dwi_json.get("EffectiveEchoSpacing")
            rmpe = dwi_json.get("ReconMatrixPE")
            if ees is not None and rmpe is not None:
                trt = ees * (rmpe - 1)
                logger.info(f"Calculated TotalReadoutTime: {trt} from EffectiveEchoSpacing and ReconMatrixPE")
            else:
                raise MissingMetadataError(
                    f"Neither 'TotalReadoutTime', nor 'EffectiveEchoSpacing' and 'ReconMatrixPE' "
                    f"found in {self.bids_layout.dwi_ap_json.name}"
                )
        
        if not isinstance(trt, (float, int)) or trt <= 0:
            raise BidsValidationError(f"Invalid 'TotalReadoutTime' value: {trt}", [f"Invalid TRT: {trt}"])
        
        return float(trt)

    def _get_delta_te(self, phasediff_json: Dict[str, Any]) -> float:
        """Extracts or calculates Delta TE for fieldmaps."""
        te1 = phasediff_json.get("EchoTime1")
        te2 = phasediff_json.get("EchoTime2")

        if te1 is None or te2 is None:
            raise MissingMetadataError(
                f"'EchoTime1' or 'EchoTime2' missing in phasediff JSON: {self.bids_layout.phasediff_json.name}"
            )
        
        delta_te = abs(float(te2) - float(te1))
        if delta_te <= 0:
            raise BidsValidationError(f"Calculated DeltaTE is non-positive: {delta_te}", [f"Invalid DeltaTE: {delta_te}"])
        
        return delta_te

    def determine_distortion_strategy(self, dwi_data: DwiData) -> DistortionStrategy:
        """
        Determines the distortion correction strategy based on available files
        and metadata.
        """
        if self.bids_layout.dwi_pa:
            # If a reverse phase-encoded DWI is found, assume RPE_PAIR
            logger.info("Detected reverse phase-encoded DWI. Using RPE_PAIR distortion correction strategy.")
            return DistortionStrategy.RPE_PAIR
        elif self.bids_layout.phasediff_nifti and dwi_data.delta_te is not None:
            # If phasediff fieldmap and DeltaTE are available, assume FIELDMAP
            logger.info("Detected phasediff fieldmap. Using FIELDMAP distortion correction strategy.")
            return DistortionStrategy.FIELDMAP
        else:
            logger.warning("No suitable data found for distortion correction. Proceeding with NONE strategy.")
            return DistortionStrategy.NONE

