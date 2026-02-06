from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class TT5GenInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 5ttgen command.
    """
    algorithm = traits.Enum(
        "fsl", "gif", "freesurfer",
        mandatory=True,
        argstr="%s",
        position=0,
        desc="Algorithm to use for 5TT segmentation."
    )
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=1,
        desc="Input T1w image."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_5tt.mif",
        keep_extension=False,
        position=2,
        argstr="%s",
        desc="Output 5TT image file."
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
    premasked = traits.Bool(
        False,
        argstr="-premasked",
        desc="Indicate that the input T1w image is already brain-extracted."
    )
    
class TT5GenOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 5ttgen command.
    """
    out_file = File(
        exists=True,
        desc="Output 5TT image file."
    )

class TT5Gen(CommandLine):
    """
    Wraps the MRtrix3 5ttgen command for 5-tissue-type segmentation.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import TT5Gen
    >>> Path("T1w_brain.nii.gz").touch()
    >>> ttgen = TT5Gen()
    >>> ttgen.inputs.algorithm = "fsl"
    >>> ttgen.inputs.in_file = "T1w_brain.nii.gz"
    >>> ttgen.inputs.out_file = "5tt.mif"
    >>> ttgen.inputs.premasked = True
    >>> ttgen.inputs.nthreads = 8
    >>> ttgen.cmdline
    '5ttgen -nthreads 8 -premasked fsl T1w_brain.nii.gz 5tt.mif'
    """
    _cmd = "5ttgen"
    input_spec = TT5GenInputSpec
    output_spec = TT5GenOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        return outputs
