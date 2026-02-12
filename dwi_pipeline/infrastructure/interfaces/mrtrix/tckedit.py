from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os


class TCKEditInputSpec(CommandLineInputSpec):
    """Input Spec for MRtrix3 tckedit command."""
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input tractography file (.tck)."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_edited.tck",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output tractography file (.tck)."
    )
    number = traits.Int(
        argstr="-number %d",
        desc="Limit output to this number of streamlines."
    )
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


class TCKEditOutputSpec(TraitedSpec):
    """Output Spec for MRtrix3 tckedit command."""
    out_file = File(
        exists=True,
        desc="Output tractography file (.tck)."
    )


class TCKEdit(CommandLine):
    """
    Wraps the MRtrix3 tckedit command for extracting/editing streamline files.

    Examples
    --------
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import TCKEdit
    >>> tckedit = TCKEdit()
    >>> tckedit.inputs.in_file = "tracts_10M.tck"
    >>> tckedit.inputs.out_file = "tracts_5k.tck"
    >>> tckedit.inputs.number = 5000
    >>> tckedit.cmdline
    'tckedit -nthreads 1 -number 5000 tracts_10M.tck tracts_5k.tck'
    """
    _cmd = "tckedit"
    input_spec = TCKEditInputSpec
    output_spec = TCKEditOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
