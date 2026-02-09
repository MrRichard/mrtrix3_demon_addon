from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os


class LabelConvertInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 labelconvert command.

    Command: labelconvert input_image in_lut out_lut output_image
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-4,
        desc="Input parcellation image (e.g. aparc+aseg from FreeSurfer)."
    )
    in_lut = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-3,
        desc="Source lookup table (e.g. FreeSurferColorLUT.txt)."
    )
    out_lut = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Target lookup table (e.g. fs_default.txt or fs_a2009s.txt)."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_parcels.mif",
        keep_extension=False,
        argstr="%s",
        position=-1,
        desc="Output converted parcellation image with sequential labels."
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


class LabelConvertOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 labelconvert command.
    """
    out_file = File(
        exists=True,
        desc="Output converted parcellation image."
    )


class LabelConvert(CommandLine):
    """
    Converts parcellation label indices from one lookup table to another.

    Typically used to convert FreeSurfer parcellation (aparc+aseg.mgz)
    from FreeSurfer's non-sequential label indices to sequential indices
    expected by tck2connectome.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix.labelconvert import LabelConvert
    >>> Path("aparc_aseg.nii.gz").touch()
    >>> Path("FreeSurferColorLUT.txt").touch()
    >>> Path("fs_default.txt").touch()
    >>> lc = LabelConvert()
    >>> lc.inputs.in_file = "aparc_aseg.nii.gz"
    >>> lc.inputs.in_lut = "FreeSurferColorLUT.txt"
    >>> lc.inputs.out_lut = "fs_default.txt"
    >>> lc.inputs.out_file = "parcels_dk.mif"
    >>> lc.inputs.force = True
    >>> lc.cmdline
    'labelconvert -force -nthreads 1 aparc_aseg.nii.gz FreeSurferColorLUT.txt fs_default.txt parcels_dk.mif'
    """
    _cmd = "labelconvert"
    input_spec = LabelConvertInputSpec
    output_spec = LabelConvertOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
