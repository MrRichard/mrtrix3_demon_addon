from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class BetInputSpec(CommandLineInputSpec):
    """
    Input Spec for FSL's bet (Brain Extraction Tool) command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=0,
        desc="Input image to be brain extracted."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_brain",
        keep_extension=True,
        position=1,
        argstr="%s",
        desc="Output brain-extracted image."
    )
    mask = traits.Bool(
        False,
        argstr="-m",
        desc="Generate a brain mask image."
    )
    frac = traits.Float(
        0.5,
        argstr="-f %f",
        desc="Fractional intensity threshold (0->1); smaller values give larger brain outline estimates."
    )
    # Other common options
    robust = traits.Bool(
        False,
        argstr="-R",
        desc="Robust brain centre estimation (iterates bet several times)."
    )
    skull = traits.Bool(
        False,
        argstr="-S",
        desc="Generate a skull image."
    )
    output_type = traits.Enum(
        "NIFTI_GZ", "NIFTI",
        argstr="-o",
        desc="Output file type.",
        default="NIFTI_GZ",
        usedefault=True,
    )
    
class BetOutputSpec(TraitedSpec):
    """
    Output Spec for FSL's bet command.
    """
    out_file = File(
        exists=True,
        desc="Brain-extracted output image."
    )
    mask_file = File(
        desc="Generated brain mask file (if mask=True)."
    )
    skull_file = File(
        desc="Generated skull file (if skull=True)."
    )

class Bet(CommandLine):
    """
    Wraps the FSL bet command for brain extraction.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.fsl import Bet
    >>> Path("T1w.nii.gz").touch()
    >>> bet = Bet()
    >>> bet.inputs.in_file = "T1w.nii.gz"
    >>> bet.inputs.out_file = "T1w_brain.nii.gz"
    >>> bet.inputs.mask = True
    >>> bet.inputs.robust = True
    >>> bet.inputs.frac = 0.4
    >>> bet.cmdline
    'bet T1w.nii.gz T1w_brain.nii.gz -m -f 0.400000 -R'
    """
    _cmd = "bet"
    input_spec = BetInputSpec
    output_spec = BetOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        if self.inputs.mask:
            # The mask file is typically named out_file_mask
            base, ext = os.path.splitext(self.inputs.out_file)
            if ext == ".gz": # Handle .nii.gz
                base, ext2 = os.path.splitext(base)
                ext = ext2 + ext
            outputs["mask_file"] = os.path.abspath(f"{base}_mask{ext}")
        if self.inputs.skull:
            # The skull file is typically named out_file_skull
            base, ext = os.path.splitext(self.inputs.out_file)
            if ext == ".gz":
                base, ext2 = os.path.splitext(base)
                ext = ext2 + ext
            outputs["skull_file"] = os.path.abspath(f"{base}_skull{ext}")
        return outputs
