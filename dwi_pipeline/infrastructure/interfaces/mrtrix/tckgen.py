from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class TCKGenInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 tckgen command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input FOD image file."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_tracts.tck",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output tractography file (.tck)."
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
    algorithm = traits.Enum(
        "iFOD2", "FACT", "iFOD1", "Nulldist1", "Nulldist2", "SD_Stream", "Seedtest", "Tensor_Det", "Tensor_Prob",
        argstr="-algorithm %s",
        default="iFOD2",
        desc="Tractography algorithm to use."
    )
    # Streamline generation options
    select = traits.Int(
        argstr="-select %d",
        desc="Set the desired number of streamlines to generate."
    )
    seed_image = File(
        exists=True,
        argstr="-seed_image %s",
        desc="Seed streamlines from an image."
    )
    seed_gmwmi = File(
        exists=True,
        argstr="-seed_gmwmi %s",
        desc="Seed from the grey matter-white matter interface (5TT format)."
    )
    act = File(
        exists=True,
        argstr="-act %s",
        desc="Use Anatomically-Constrained Tractography (5TT format)."
    )
    backtrack = traits.Bool(
        True,
        argstr="-backtrack",
        usedefault=True,
        desc="Allow streamlines to be tracked in both directions from the seed."
    )
    crop_at_gmwmi = traits.Bool(
        True,
        argstr="-crop_at_gmwmi",
        usedefault=True,
        desc="Crop streamlines at the grey matter-white matter interface (requires -act)."
    )
    # Other options
    cutoff = traits.Float(
        argstr="-cutoff %f",
        desc="FOD amplitude cutoff for terminating tracks."
    )
    minlength = traits.Float(
        argstr="-minlength %f",
        desc="Minimum length of any streamline in mm."
    )
    maxlength = traits.Float(
        argstr="-maxlength %f",
        desc="Maximum length of any streamline in mm."
    )
    power = traits.Int(
        argstr="-power %d",
        desc="Exponent for FOD-based tractography algorithms."
    )
    step = traits.Float(
        argstr="-step %f",
        desc="Step size of the tractography algorithm in mm."
    )
    
class TCKGenOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 tckgen command.
    """
    out_file = File(
        exists=True,
        desc="Output tractography file (.tck)."
    )

class TCKGen(CommandLine):
    """
    Performs streamline tractography from FODs.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import TCKGen
    >>> Path("fod.mif").touch()
    >>> Path("gmwmi.mif").touch()
    >>> tckgen = TCKGen()
    >>> tckgen.inputs.in_file = "fod.mif"
    >>> tckgen.inputs.out_file = "tracts_10M.tck"
    >>> tckgen.inputs.algorithm = "iFOD2"
    >>> tckgen.inputs.select = 10000000
    >>> tckgen.inputs.seed_gmwmi = "gmwmi.mif"
    >>> tckgen.inputs.nthreads = 8
    >>> tckgen.cmdline
    'tckgen -nthreads 8 -algorithm iFOD2 -select 10000000 -seed_gmwmi gmwmi.mif fod.mif tracts_10M.tck'
    """
    _cmd = "tckgen"
    input_spec = TCKGenInputSpec
    output_spec = TCKGenOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
