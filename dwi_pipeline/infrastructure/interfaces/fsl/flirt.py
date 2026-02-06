from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class FlirtInputSpec(CommandLineInputSpec):
    """
    Input Spec for FSL's flirt command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="-in %s",
        desc="Input volume."
    )
    reference = File(
        exists=True,
        mandatory=True,
        argstr="-ref %s",
        desc="Reference volume."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_flirt.nii.gz",
        keep_extension=True,
        argstr="-out %s",
        desc="Output registered volume."
    )
    out_matrix_file = File(
        name_source="in_file",
        name_template="%s_flirt.mat",
        keep_extension=False,
        argstr="-omat %s",
        desc="Output transformation matrix."
    )
    # Registration options
    dof = traits.Enum(
        6, 7, 9, 12,
        argstr="-dof %d",
        desc="Degrees of freedom (6=rigid, 7=scale, 9=affine, 12=full affine)."
    )
    cost = traits.Enum(
        "mutualinfo", "corratio", "normcorr", "normmi", "leastsq",
        argstr="-cost %s",
        desc="Cost function for registration."
    )
    searchr_x = traits.Tuple(
        traits.Int, traits.Int,
        argstr="-searchrx %d %d",
        desc="Search range for rotation about x-axis (degrees)."
    )
    searchr_y = traits.Tuple(
        traits.Int, traits.Int,
        argstr="-searchry %d %d",
        desc="Search range for rotation about y-axis (degrees)."
    )
    searchr_z = traits.Tuple(
        traits.Int, traits.Int,
        argstr="-searchrz %d %d",
        desc="Search range for rotation about z-axis (degrees)."
    )
    apply_xfm = traits.Bool(
        argstr="-applyxfm",
        desc="Apply existing transform."
    )
    init = File(
        exists=True,
        argstr="-init %s",
        desc="Input transformation matrix."
    )
    interp = traits.Enum(
        "trilinear", "nearestneighbour", "sinc", "spline",
        argstr="-interp %s",
        desc="Interpolation method."
    )

class FlirtOutputSpec(TraitedSpec):
    """
    Output Spec for FSL's flirt command.
    """
    out_file = File(
        exists=True,
        desc="Registered output volume."
    )
    out_matrix_file = File(
        exists=True,
        desc="Output transformation matrix."
    )

class Flirt(CommandLine):
    """
    Wraps the FSL flirt command for linear image registration.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.fsl import Flirt
    >>> Path("t1.nii.gz").touch()
    >>> Path("dwi_b0.nii.gz").touch()
    >>> flirt = Flirt()
    >>> flirt.inputs.in_file = "t1.nii.gz"
    >>> flirt.inputs.reference = "dwi_b0.nii.gz"
    >>> flirt.inputs.out_file = "t1_reg.nii.gz"
    >>> flirt.inputs.out_matrix_file = "t1_reg.mat"
    >>> flirt.inputs.dof = 6
    >>> flirt.inputs.cost = "mutualinfo"
    >>> flirt.cmdline
    'flirt -in t1.nii.gz -ref dwi_b0.nii.gz -out t1_reg.nii.gz -omat t1_reg.mat -dof 6 -cost mutualinfo'
    """
    _cmd = "flirt"
    input_spec = FlirtInputSpec
    output_spec = FlirtOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        if self.inputs.out_matrix_file:
            outputs["out_matrix_file"] = os.path.abspath(self.inputs.out_matrix_file)
        return outputs
