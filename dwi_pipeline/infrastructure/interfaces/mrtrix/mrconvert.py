from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class MRConvertInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 mrconvert command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input image file."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output image file (MIF format recommended for MRtrix3)."
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
    # DWI-specific options
    fslgrad = traits.Tuple(
        File(exists=True),
        File(exists=True),
        argstr="-fslgrad %s %s",
        desc="Specify gradient table in FSL format (bvecs, bvals)."
    )
    json_sidecar = File(
        exists=True,
        argstr="-json_import %s",
        desc="Import header information from a JSON file (BIDS sidecar)."
    )
    # Data type options
    datatype = traits.Str(
        argstr="-datatype %s",
        desc="Specify output image data type (e.g., float32, float64, int32). Only added when explicitly set."
    )


class MRConvertOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 mrconvert command.
    """
    out_file = File(
        exists=True,
        desc="Converted output image file."
    )

class MRConvert(CommandLine):
    """
    Converts images between different formats, extracts/inserts DWI gradient
    information, and can also apply various image processing options.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import MRConvert
    >>> # Create dummy files for demonstration
    >>> Path("dwi.nii.gz").touch()
    >>> Path("dwi.bval").touch()
    >>> Path("dwi.bvec").touch()
    >>> mrconv = MRConvert()
    >>> mrconv.inputs.in_file = "dwi.nii.gz"
    >>> mrconv.inputs.out_file = "dwi.mif"
    >>> mrconv.inputs.fslgrad = ("dwi.bvec", "dwi.bval")
    >>> mrconv.inputs.nthreads = 4
    >>> mrconv.cmdline
    'mrconvert -nthreads 4 -fslgrad dwi.bvec dwi.bval dwi.nii.gz dwi.mif'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # mrconv.run()
    """
    _cmd = "mrconvert"
    input_spec = MRConvertInputSpec
    output_spec = MRConvertOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        return outputs

