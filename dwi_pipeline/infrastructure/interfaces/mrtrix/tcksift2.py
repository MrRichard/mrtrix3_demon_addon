from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class TckSift2InputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 tcksift2 command.
    """
    in_tracks = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=0,
        desc="Input tractography file."
    )
    in_fod = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=1,
        desc="Input FOD image."
    )
    out_weights = File(
        name_source="in_tracks",
        name_template="%s_sift_weights.txt",
        keep_extension=False,
        position=2,
        argstr="%s",
        desc="Output streamline weights file."
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
    act = File(
        exists=True,
        argstr="-act %s",
        desc="Use Anatomically-Constrained Tractography (5TT format)."
    )
    fd_scale_gm = traits.Bool(
        False,
        argstr="-fd_scale_gm",
        desc="Scale FODs by the gray-matter volume fraction in each voxel."
    )

class TckSift2OutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 tcksift2 command.
    """
    out_weights = File(
        exists=True,
        desc="Output streamline weights file."
    )

class TckSift2(CommandLine):
    """
    Wraps the MRtrix3 tcksift2 command for streamline filtering.
    """
    _cmd = "tcksift2"
    input_spec = TckSift2InputSpec
    output_spec = TckSift2OutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_weights):
            outputs["out_weights"] = os.path.abspath(self.inputs.out_weights)
        else:
            outputs["out_weights"] = os.path.abspath(self._filename_from_source("out_weights"))
        return outputs
