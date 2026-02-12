from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWI2MaskInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwi2mask command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input DWI image file (MIF format)."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_mask.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output brain mask image file."
    )
    # Generic options
    force = traits.Bool(
        False,
        argstr="-force",
        desc="Overwrite existing output files."
    )
    nthreads = traits.Int(
        1,
        argstr="-nthreads %d",
        desc="Number of threads to use for computation."
    )
    # DWI mask options
    clean_scale = traits.Float(
        argstr="-clean_scale %f",
        desc="Set the scale factor for the mask clean-up operation."
    )

class DWI2MaskOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwi2mask command.
    """
    out_file = File(
        exists=True,
        desc="Output brain mask image file."
    )

class DWI2Mask(CommandLine):
    """
    Generates a brain mask from DWI data.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWI2Mask
    >>> # Create dummy files for demonstration
    >>> Path("dwi.mif").touch()
    >>> mask = DWI2Mask()
    >>> mask.inputs.in_file = "dwi.mif"
    >>> mask.inputs.out_file = "mask.mif"
    >>> mask.inputs.nthreads = 4
    >>> mask.cmdline
    'dwi2mask -nthreads 4 dwi.mif mask.mif'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # mask.run()
    """
    _cmd = "dwi2mask"
    input_spec = DWI2MaskInputSpec
    output_spec = DWI2MaskOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
