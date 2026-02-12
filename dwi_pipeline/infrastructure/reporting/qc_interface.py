"""
Nipype SimpleInterface wrappers for QC image generation.
"""
from __future__ import annotations

from nipype.interfaces.base import (
    SimpleInterface, BaseInterfaceInputSpec, TraitedSpec,
    File, Directory, traits, isdefined,
)

from .qc_generator import generate_overlay_qc, generate_tract_qc


# --------------------------------------------------------------------------- #
#  Overlay QC
# --------------------------------------------------------------------------- #

class _OverlayQCInputSpec(BaseInterfaceInputSpec):
    b0_nii = File(exists=True, mandatory=True, desc="b0 volume (NIfTI)")
    mask_nii = File(exists=True, mandatory=True, desc="Binary brain mask (NIfTI)")
    fivett_nii = File(exists=True, mandatory=True, desc="5TT tissue image (NIfTI)")
    brain_nii = File(exists=True, mandatory=True, desc="Registered brain (NIfTI)")
    parc_dk_nii = File(exists=True, mandatory=True, desc="DK parcellation in DWI space (NIfTI)")
    parc_destrieux_nii = File(desc="Destrieux parcellation in DWI space (NIfTI, optional)")
    out_dir = Directory(mandatory=True, desc="Output directory for QC PNGs")


class _OverlayQCOutputSpec(TraitedSpec):
    brain_mask_qc = File(desc="Brain mask QC image")
    fivett_qc = File(desc="5TT tissue segmentation QC image")
    registration_qc = File(desc="Registration QC image")
    parcellation_dk_qc = File(desc="DK atlas QC image")
    parcellation_destrieux_qc = File(desc="Destrieux atlas QC image (may not exist)")


class OverlayQC(SimpleInterface):
    """Generate overlay QC images (mask, 5TT, registration, parcellation)."""
    input_spec = _OverlayQCInputSpec
    output_spec = _OverlayQCOutputSpec

    def _run_interface(self, runtime):
        parc_dest = None
        if isdefined(self.inputs.parc_destrieux_nii):
            parc_dest = self.inputs.parc_destrieux_nii

        paths = generate_overlay_qc(
            b0_nii=self.inputs.b0_nii,
            mask_nii=self.inputs.mask_nii,
            fivett_nii=self.inputs.fivett_nii,
            brain_nii=self.inputs.brain_nii,
            parc_dk_nii=self.inputs.parc_dk_nii,
            parc_destrieux_nii=parc_dest,
            out_dir=self.inputs.out_dir,
        )

        self._results["brain_mask_qc"] = paths["brain_mask_qc"]
        self._results["fivett_qc"] = paths["5tt_qc"]
        self._results["registration_qc"] = paths["registration_qc"]
        self._results["parcellation_dk_qc"] = paths["parcellation_dk_qc"]
        if "parcellation_destrieux_qc" in paths:
            self._results["parcellation_destrieux_qc"] = paths["parcellation_destrieux_qc"]

        return runtime


# --------------------------------------------------------------------------- #
#  Tract QC
# --------------------------------------------------------------------------- #

class _TractQCInputSpec(BaseInterfaceInputSpec):
    b0_nii = File(exists=True, mandatory=True, desc="b0 volume (NIfTI)")
    tck_file = File(exists=True, mandatory=True, desc="Tractography file (.tck)")
    out_dir = Directory(mandatory=True, desc="Output directory for QC PNGs")


class _TractQCOutputSpec(TraitedSpec):
    tracts_sagittal_qc = File(desc="Sagittal tract QC image")
    tracts_coronal_qc = File(desc="Coronal tract QC image")
    tracts_axial_qc = File(desc="Axial tract QC image")


class TractQC(SimpleInterface):
    """Generate tractography QC images (sagittal, coronal, axial projections)."""
    input_spec = _TractQCInputSpec
    output_spec = _TractQCOutputSpec

    def _run_interface(self, runtime):
        paths = generate_tract_qc(
            b0_nii=self.inputs.b0_nii,
            tck_file=self.inputs.tck_file,
            out_dir=self.inputs.out_dir,
        )

        self._results["tracts_sagittal_qc"] = paths["tracts_sagittal_qc"]
        self._results["tracts_coronal_qc"] = paths["tracts_coronal_qc"]
        self._results["tracts_axial_qc"] = paths["tracts_axial_qc"]

        return runtime
