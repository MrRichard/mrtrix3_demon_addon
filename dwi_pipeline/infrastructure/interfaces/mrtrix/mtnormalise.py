from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os


class MtNormaliseInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 mtnormalise command.

    Command syntax: mtnormalise in_wm out_wm [in_gm out_gm] [in_csf out_csf] -mask mask
    """
    in_wm = File(
        exists=True,
        mandatory=True,
        desc="Input white matter FOD image."
    )
    out_wm = File(
        "wmfod_norm.mif",
        usedefault=True,
        desc="Output normalised white matter FOD image."
    )
    in_gm = File(
        exists=True,
        desc="Input gray matter FOD image (multi-shell only)."
    )
    out_gm = File(
        "gmfod_norm.mif",
        usedefault=True,
        desc="Output normalised gray matter FOD image."
    )
    in_csf = File(
        exists=True,
        desc="Input CSF FOD image (multi-shell only)."
    )
    out_csf = File(
        "csffod_norm.mif",
        usedefault=True,
        desc="Output normalised CSF FOD image."
    )
    mask = File(
        exists=True,
        mandatory=True,
        argstr="-mask %s",
        desc="Brain mask image."
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


class MtNormaliseOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 mtnormalise command.
    """
    out_wm = File(exists=True, desc="Normalised white matter FOD image.")
    out_gm = File(desc="Normalised gray matter FOD image.")
    out_csf = File(desc="Normalised CSF FOD image.")


class MtNormalise(CommandLine):
    """
    Performs multi-tissue informed intensity normalisation of FOD images.

    For single-shell data: normalises WM FOD only.
    For multi-shell data: normalises WM, GM, and CSF FODs jointly.

    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix.mtnormalise import MtNormalise
    >>> Path("wmfod.mif").touch()
    >>> Path("mask.mif").touch()
    >>> norm = MtNormalise()
    >>> norm.inputs.in_wm = "wmfod.mif"
    >>> norm.inputs.mask = "mask.mif"
    >>> norm.cmdline
    'mtnormalise -nthreads 1 -mask mask.mif wmfod.mif wmfod_norm.mif'
    """
    _cmd = "mtnormalise"
    input_spec = MtNormaliseInputSpec
    output_spec = MtNormaliseOutputSpec

    @property
    def cmdline(self):
        cmd = [self._cmd]

        # Generic options first
        if self.inputs.force:
            cmd.append("-force")
        if self.inputs.nthreads:
            cmd.append(f"-nthreads {self.inputs.nthreads}")
        if self.inputs.mask:
            cmd.append(f"-mask {self.inputs.mask}")

        # Positional args: in_wm out_wm [in_gm out_gm] [in_csf out_csf]
        cmd.extend([self.inputs.in_wm, self.inputs.out_wm])
        if self.inputs.in_gm:
            cmd.extend([self.inputs.in_gm, self.inputs.out_gm])
        if self.inputs.in_csf:
            cmd.extend([self.inputs.in_csf, self.inputs.out_csf])

        return " ".join(cmd)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_wm"] = os.path.abspath(self.inputs.out_wm)
        if self.inputs.in_gm:
            outputs["out_gm"] = os.path.abspath(self.inputs.out_gm)
        if self.inputs.in_csf:
            outputs["out_csf"] = os.path.abspath(self.inputs.out_csf)
        return outputs
