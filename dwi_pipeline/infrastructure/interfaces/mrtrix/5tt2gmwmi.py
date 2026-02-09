from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class TT5ToGMWMIInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 5tt2gmwmi command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=0,
        desc="Input 5TT image."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_gmwmi.mif",
        keep_extension=False,
        position=1,
        argstr="%s",
        desc="Output GM-WM interface image."
    )
    # Generic options
    force = traits.Bool(
        False,
        argstr="-force",
        desc="Overwrite existing output files."
    )
    
class TT5ToGMWMIOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 5tt2gmwmi command.
    """
    out_file = File(
        exists=True,
        desc="Output GM-WM interface image."
    )

class TT5ToGMWMI(CommandLine):
    """
    Wraps the MRtrix3 5tt2gmwmi command to generate a GM-WM interface image.
    """
    _cmd = "5tt2gmwmi"
    input_spec = TT5ToGMWMIInputSpec
    output_spec = TT5ToGMWMIOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
