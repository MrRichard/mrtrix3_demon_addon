from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWI2FODInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwi2fod command.
    """
    algorithm = traits.Enum(
        "csd", "msmt_csd",
        argstr="%s",
        position=-4,
        desc="Algorithm to use for FOD estimation."
    )
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-3,
        desc="Input DWI image file (MIF format)."
    )
    # For CSD
    response = File(
        exists=True,
        argstr="%s",
        position=-2,
        desc="Response function text file."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_fod.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output FOD image file."
    )
    # For MSMT-CSD
    wm_response = File(
        exists=True,
        argstr="%s",
        desc="White matter response function (msmt_csd)."
    )
    gm_response = File(
        exists=True,
        argstr="%s",
        desc="Gray matter response function (msmt_csd)."
    )
    csf_response = File(
        exists=True,
        argstr="%s",
        desc="CSF response function (msmt_csd)."
    )
    wm_odf = File(
        name_source="in_file",
        name_template="%s_wm_fod.mif",
        keep_extension=False,
        argstr="%s",
        desc="Output white matter FOD image (msmt_csd)."
    )
    gm_odf = File(
        name_source="in_file",
        name_template="%s_gm_fod.mif",
        keep_extension=False,
        argstr="%s",
        desc="Output gray matter FOD image (msmt_csd)."
    )
    csf_odf = File(
        name_source="in_file",
        name_template="%s_csf_fod.mif",
        keep_extension=False,
        argstr="%s",
        desc="Output CSF FOD image (msmt_csd)."
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
    mask = File(
        exists=True,
        argstr="-mask %s",
        desc="Provide a brain mask."
    )

class DWI2FODOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwi2fod command.
    """
    out_file = File(exists=True, desc="Output FOD image file.")
    wm_odf = File(desc="Output white matter FOD image (msmt_csd).")
    gm_odf = File(desc="Output gray matter FOD image (msmt_csd).")
    csf_odf = File(desc="Output CSF FOD image (msmt_csd).")

class DWI2FOD(CommandLine):
    """
    Estimates Fiber Orientation Distributions (FODs) from DWI data.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWI2FOD
    >>> # CSD example
    >>> Path("dwi.mif").touch()
    >>> Path("response.txt").touch()
    >>> Path("mask.mif").touch()
    >>> csd = DWI2FOD()
    >>> csd.inputs.algorithm = "csd"
    >>> csd.inputs.in_file = "dwi.mif"
    >>> csd.inputs.response = "response.txt"
    >>> csd.inputs.out_file = "fod.mif"
    >>> csd.inputs.mask = "mask.mif"
    >>> csd.inputs.nthreads = 8
    >>> csd.cmdline
    'dwi2fod -nthreads 8 -mask mask.mif csd dwi.mif response.txt fod.mif'
    
    >>> # MSMT-CSD example
    >>> msmt = DWI2FOD()
    >>> msmt.inputs.algorithm = "msmt_csd"
    >>> msmt.inputs.in_file = "dwi.mif"
    >>> msmt.inputs.wm_response = "wm.txt"
    >>> msmt.inputs.wm_odf = "wm_fod.mif"
    >>> msmt.inputs.gm_response = "gm.txt"
    >>> msmt.inputs.gm_odf = "gm_fod.mif"
    >>> msmt.inputs.csf_response = "csf.txt"
    >>> msmt.inputs.csf_odf = "csf_fod.mif"
    >>> msmt.inputs.mask = "mask.mif"
    >>> msmt.cmdline
    'dwi2fod -mask mask.mif msmt_csd dwi.mif wm.txt wm_fod.mif gm.txt gm_fod.mif csf.txt csf_fod.mif'
    """
    _cmd = "dwi2fod"
    input_spec = DWI2FODInputSpec
    output_spec = DWI2FODOutputSpec

    @property
    def cmdline(self):
        cmd = [self._cmd]
        
        # Generic options first
        if self.inputs.force:
            cmd.append("-force")
        if self.inputs.nthreads > 1:
            cmd.append(f"-nthreads {self.inputs.nthreads}")
        if isdefined(self.inputs.mask):
            cmd.append(f"-mask {self.inputs.mask}")
        
        # Algorithm and positional arguments
        cmd.append(self.inputs.algorithm)
        cmd.append(self.inputs.in_file)

        if self.inputs.algorithm == 'csd':
            cmd.append(self.inputs.response)
            cmd.append(self.inputs.out_file)
        elif self.inputs.algorithm == 'msmt_csd':
            cmd.extend([self.inputs.wm_response, self.inputs.wm_odf])
            if isdefined(self.inputs.gm_response) and isdefined(self.inputs.gm_odf):
                cmd.extend([self.inputs.gm_response, self.inputs.gm_odf])
            if isdefined(self.inputs.csf_response) and isdefined(self.inputs.csf_odf):
                cmd.extend([self.inputs.csf_response, self.inputs.csf_odf])
        else:
            raise ValueError(f"Unsupported algorithm: {self.inputs.algorithm}")

        return " ".join(cmd)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if self.inputs.algorithm == 'csd':
            if isdefined(self.inputs.out_file):
                outputs["out_file"] = os.path.abspath(self.inputs.out_file)
            else:
                outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        elif self.inputs.algorithm == 'msmt_csd':
            if isdefined(self.inputs.wm_odf):
                outputs["wm_odf"] = os.path.abspath(self.inputs.wm_odf)
            else:
                outputs["wm_odf"] = os.path.abspath(self._filename_from_source("wm_odf"))
            if isdefined(self.inputs.gm_odf):
                outputs["gm_odf"] = os.path.abspath(self.inputs.gm_odf)
            if isdefined(self.inputs.csf_odf):
                outputs["csf_odf"] = os.path.abspath(self.inputs.csf_odf)
            # Set the primary output to be the WM ODF for downstream processing
            outputs["out_file"] = outputs["wm_odf"]
        return outputs
