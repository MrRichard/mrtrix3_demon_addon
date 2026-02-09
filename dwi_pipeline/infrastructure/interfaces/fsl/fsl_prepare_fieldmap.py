from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class FSLPrepareFieldmapInputSpec(CommandLineInputSpec):
    """
    Input Spec for FSL's fsl_prepare_fieldmap command.
    """
    in_phase = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=2,
        desc="Input phase difference image (raw scanner values)."
    )
    in_magnitude = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=3,
        desc="Input magnitude image (brain extracted)."
    )
    out_fieldmap = File(
        name_source="in_phase",
        name_template="%s_fieldmap",
        keep_extension=True,
        position=4,
        argstr="%s",
        desc="Output fieldmap image in rad/s."
    )
    delta_te = traits.Float(
        mandatory=True,
        argstr="%f",
        position=5,
        desc="Echo time difference (in ms)."
    )
    # Options
    nocheck = traits.Bool(
        False,
        argstr="--nocheck",
        desc="Turn off check for EPI sequence."
    )
    scanner = traits.Enum(
        "SIEMENS", "PHILIPS", "GE", "BRUKER", "CANON",
        argstr="--scanner=%s",
        desc="Scanner type."
    )
    
class FSLPrepareFieldmapOutputSpec(TraitedSpec):
    """
    Output Spec for FSL's fsl_prepare_fieldmap command.
    """
    out_fieldmap = File(
        exists=True,
        desc="Output fieldmap image in rad/s."
    )

class FSLPrepareFieldmap(CommandLine):
    """
    Wraps the FSL fsl_prepare_fieldmap command.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.fsl import FSLPrepareFieldmap
    >>> Path("phase.nii.gz").touch()
    >>> Path("magnitude_brain.nii.gz").touch()
    >>> prep = FSLPrepareFieldmap()
    >>> prep.inputs.in_phase = "phase.nii.gz"
    >>> prep.inputs.in_magnitude = "magnitude_brain.nii.gz"
    >>> prep.inputs.out_fieldmap = "fieldmap.nii.gz"
    >>> prep.inputs.delta_te = 2.46
    >>> prep.cmdline
    'fsl_prepare_fieldmap SIEMENS phase.nii.gz magnitude_brain.nii.gz fieldmap.nii.gz 2.460000'
    """
    _cmd = "fsl_prepare_fieldmap"
    input_spec = FSLPrepareFieldmapInputSpec
    output_spec = FSLPrepareFieldmapOutputSpec
    
    def __init__(self, **inputs):
        # fsl_prepare_fieldmap requires scanner type as the first argument,
        # but Nipype CommandLine positions arguments based on order in InputSpec.
        # We can prepend the scanner argument manually here or adjust argstr.
        # A simple approach is to use a default for the first positional argument.
        super(FSLPrepareFieldmap, self).__init__(**inputs)
        # Default scanner to SIEMENS if not specified
        if not self.inputs.scanner:
            self.inputs.scanner = "SIEMENS"

    def _format_arg(self, name, spec, value):
        # Override to handle the scanner argument which is the first positional argument
        if name == 'scanner':
             return value # scanner is the first positional argument
        return super(FSLPrepareFieldmap, self)._format_arg(name, spec, value)

    @property
    def cmdline(self):
        # Manually construct command line to ensure correct argument order
        cmd = [self._cmd]
        if self.inputs.scanner:
            cmd.append(self.inputs.scanner)
        cmd.append(self.inputs.in_phase)
        cmd.append(self.inputs.in_magnitude)
        cmd.append(self.inputs.out_fieldmap)
        cmd.append(str(self.inputs.delta_te))
        if self.inputs.nocheck:
            cmd.append("--nocheck")
        return " ".join(cmd)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_fieldmap):
            outputs["out_fieldmap"] = os.path.abspath(self.inputs.out_fieldmap)
        else:
            outputs["out_fieldmap"] = os.path.abspath(self._filename_from_source("out_fieldmap"))
        return outputs
