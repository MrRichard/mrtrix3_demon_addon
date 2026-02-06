from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class MRDeGibbsInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 mrdegibbs command.
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
        name_template="%s_degibbs.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output Gibbs ringing corrected DWI image file."
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
    axes = traits.Tuple(
        traits.Int, traits.Int,
        argstr="-axes %d,%d",
        desc="Specify the axes to perform Gibbs ringing correction along. (default: 0,1)"
    )
    minW = traits.Int(
        3,
        argstr="-minW %d",
        desc="Minimum number of samples for windowing."
    )
    maxW = traits.Int(
        25,
        argstr="-maxW %d",
        desc="Maximum number of samples for windowing."
    )

class MRDeGibbsOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 mrdegibbs command.
    """
    out_file = File(
        exists=True,
        desc="Gibbs ringing corrected DWI image file."
    )

class MRDeGibbs(CommandLine):
    """
    Removes Gibbs ringing artifacts from DWI data.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import MRDeGibbs
    >>> # Create dummy files for demonstration
    >>> Path("dwi_den.mif").touch()
    >>> degibbs = MRDeGibbs()
    >>> degibbs.inputs.in_file = "dwi_den.mif"
    >>> degibbs.inputs.out_file = "dwi_den_degibbs.mif"
    >>> degibbs.inputs.nthreads = 4
    >>> degibbs.cmdline
    'mrdegibbs -nthreads 4 dwi_den.mif dwi_den_degibbs.mif'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # degibbs.run()
    """
    _cmd = "mrdegibbs"
    input_spec = MRDeGibbsInputSpec
    output_spec = MRDeGibbsOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        return outputs
