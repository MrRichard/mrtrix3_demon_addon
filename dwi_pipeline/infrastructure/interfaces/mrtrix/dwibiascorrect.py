from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class DWIBiasCorrectInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwibiascorrect command.
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
        name_template="%s_unbiased.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output bias-corrected DWI image file."
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
    # Algorithm options
    use_ants = traits.Bool(
        False,
        argstr="-ants",
        desc="Use ANTs N4BiasFieldCorrection (recommended)."
    )
    use_fsl = traits.Bool(
        False,
        argstr="-fsl",
        desc="Use FSL FAST for bias field correction."
    )
    # Algorithm-specific options
    ants_args = traits.Str(
        argstr='-ants_args "%s"',
        desc="Additional arguments to pass to ANTs N4BiasFieldCorrection command."
    )
    fsl_args = traits.Str(
        argstr='-fsl_args "%s"',
        desc="Additional arguments to pass to FSL FAST command."
    )
    bias = File(
        name_source="in_file",
        name_template="%s_biasfield.mif",
        keep_extension=False,
        argstr="-bias %s",
        desc="Output the estimated bias field."
    )
    mask = File(
        exists=True,
        argstr="-mask %s",
        desc="Provide a brain mask to constrain the bias field estimation."
    )

class DWIBiasCorrectOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwibiascorrect command.
    """
    out_file = File(
        exists=True,
        desc="Bias-corrected DWI image file."
    )
    bias = File(
        desc="Estimated bias field."
    )

class DWIBiasCorrect(CommandLine):
    """
    Performs B1 bias field correction on DWI data.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWIBiasCorrect
    >>> # Create dummy files for demonstration
    >>> Path("dwi.mif").touch()
    >>> Path("mask.mif").touch()
    >>> biascorrect = DWIBiasCorrect()
    >>> biascorrect.inputs.in_file = "dwi.mif"
    >>> biascorrect.inputs.out_file = "dwi_unbiased.mif"
    >>> biascorrect.inputs.bias = "bias.mif"
    >>> biascorrect.inputs.use_ants = True
    >>> biascorrect.inputs.mask = "mask.mif"
    >>> biascorrect.inputs.nthreads = 8
    >>> biascorrect.cmdline
    'dwibiascorrect -nthreads 8 -ants dwi.mif dwi_unbiased.mif -bias bias.mif -mask mask.mif'
    >>> # Run this for real if MRtrix3 and ANTs are installed and in PATH
    >>> # biascorrect.run()
    """
    _cmd = "dwibiascorrect"
    input_spec = DWIBiasCorrectInputSpec
    output_spec = DWIBiasCorrectOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        if self.inputs.bias:
            outputs["bias"] = os.path.abspath(self.inputs.bias)
        return outputs
