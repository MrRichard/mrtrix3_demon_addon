from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWIDenoiseInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwidenoise command.
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
        name_template="%s_denoised.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output denoised DWI image file."
    )
    noise = File(
        name_source="in_file",
        name_template="%s_noise.mif",
        keep_extension=False,
        argstr="-noise %s",
        desc="Output image of the estimated noise map."
    )
    mask = File(
        exists=True,
        argstr="-mask %s",
        desc="Mask image to exclude non-brain tissue from noise estimation."
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
    # Algorithm parameters
    extent = traits.Tuple(
        traits.Int, traits.Int, traits.Int,
        argstr="-extent %d,%d,%d",
        desc="Specify the extent of the local PCA neighbourhood. (default: 5,5,5)"
    )
    estimator = traits.Enum(
        "Exp1", "Exp2",
        argstr="-estimator %s",
        desc="Select the noise level estimator."
    )
    debug = traits.Bool(
        False,
        argstr="-debug",
        desc="Enable debugging output (extra images etc.)."
    )

class DWIDenoiseOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwidenoise command.
    """
    out_file = File(
        exists=True,
        desc="Denoised output DWI image file."
    )
    noise = File(
        exists=True,
        desc="Output image of the estimated noise map."
    )

class DWIDenoise(CommandLine):
    """
    Denoises DWI data using the MP-PCA algorithm.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWIDenoise
    >>> # Create dummy files for demonstration
    >>> Path("dwi.mif").touch()
    >>> denoise = DWIDenoise()
    >>> denoise.inputs.in_file = "dwi.mif"
    >>> denoise.inputs.out_file = "dwi_den.mif"
    >>> denoise.inputs.noise = "noise.mif"
    >>> denoise.inputs.nthreads = 4
    >>> denoise.cmdline
    'dwidenoise -nthreads 4 dwi.mif dwi_den.mif -noise noise.mif'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # denoise.run()
    """
    _cmd = "dwidenoise"
    input_spec = DWIDenoiseInputSpec
    output_spec = DWIDenoiseOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        if isdefined(self.inputs.noise):
            outputs["noise"] = os.path.abspath(self.inputs.noise)
        return outputs
