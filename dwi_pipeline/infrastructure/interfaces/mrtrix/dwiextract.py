from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWIExtractInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwiextract command.
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
        name_template="%s_extracted.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output extracted image file."
    )
    bzero = traits.Bool(
        False,
        argstr="-bzero",
        desc="Extract b-zero images."
    )
    nobzero = traits.Bool(
        False,
        argstr="-nobzero",
        desc="Extract all non-b-zero images."
    )
    
class DWIExtractOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwiextract command.
    """
    out_file = File(
        exists=True,
        desc="Output extracted image file."
    )

class DWIExtract(CommandLine):
    """
    Wraps the MRtrix3 dwiextract command.
    """
    _cmd = "dwiextract"
    input_spec = DWIExtractInputSpec
    output_spec = DWIExtractOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
