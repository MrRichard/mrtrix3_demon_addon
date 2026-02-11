from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWI2ResponseInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwi2response command.

    Modern MRtrix3 syntax: dwi2response algorithm input [output] [options]
    The algorithm is a positional sub-command, not a flag.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        desc="Input DWI image file (MIF format)."
    )
    algorithm = traits.Enum(
        "tournier", "dhollander", "fa", "tax", "manual",
        mandatory=True,
        desc="Algorithm to use for response function estimation."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_response.txt",
        keep_extension=False,
        desc="Output response function text file (tournier/fa/tax/manual)."
    )
    # Generic options
    force = traits.Bool(
        False,
        desc="Overwrite existing output files."
    )
    nthreads = traits.Int(
        1,
        desc="Number of threads to use for computation."
    )
    # Algorithm parameters
    mask = File(
        exists=True,
        desc="Provide a brain mask."
    )
    voxels = File(
        desc="Output a mask containing the voxels selected by the algorithm."
    )
    # dhollander-specific options
    wm_file = File(
        name_source="in_file",
        name_template="%s_wm_response.txt",
        keep_extension=False,
        desc="White matter response function (dhollander)."
    )
    gm_file = File(
        name_source="in_file",
        name_template="%s_gm_response.txt",
        keep_extension=False,
        desc="Gray matter response function (dhollander)."
    )
    csf_file = File(
        name_source="in_file",
        name_template="%s_csf_response.txt",
        keep_extension=False,
        desc="CSF response function (dhollander)."
    )

class DWI2ResponseOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwi2response command.
    """
    out_file = File(
        exists=True,
        desc="Output response function text file."
    )
    wm_file = File(desc="White matter response function (dhollander).")
    gm_file = File(desc="Gray matter response function (dhollander).")
    csf_file = File(desc="CSF response function (dhollander).")
    voxels = File(desc="Mask image of selected voxels.")

class DWI2Response(CommandLine):
    """
    Estimates the fiber response function for CSD.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWI2Response
    >>> # Create dummy files for demonstration
    >>> Path("dwi.mif").touch()
    >>> Path("mask.mif").touch()
    >>> response = DWI2Response()
    >>> response.inputs.in_file = "dwi.mif"
    >>> response.inputs.algorithm = "tournier"
    >>> response.inputs.out_file = "response.txt"
    >>> response.inputs.mask = "mask.mif"
    >>> response.inputs.nthreads = 4
    >>> response.cmdline
    'dwi2response tournier dwi.mif response.txt -force -nthreads 4 -mask mask.mif'
    >>> # For dhollander
    >>> response2 = DWI2Response()
    >>> Path("dwi.mif").touch()
    >>> Path("mask.mif").touch()
    >>> response2.inputs.in_file = "dwi.mif"
    >>> response2.inputs.algorithm = "dhollander"
    >>> response2.inputs.wm_file = "wm_response.txt"
    >>> response2.inputs.gm_file = "gm_response.txt"
    >>> response2.inputs.csf_file = "csf_response.txt"
    >>> response2.inputs.mask = "mask.mif"
    >>> response2.inputs.nthreads = 4
    >>> response2.cmdline
    'dwi2response dhollander dwi.mif wm_response.txt gm_response.txt csf_response.txt -force -nthreads 4 -mask mask.mif'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # response.run()
    """
    _cmd = "dwi2response"
    input_spec = DWI2ResponseInputSpec
    output_spec = DWI2ResponseOutputSpec

    @property
    def cmdline(self):
        """Build command line with algorithm as positional sub-command."""
        cmd = [self._cmd]

        # Algorithm (positional sub-command) and input file
        cmd.append(self.inputs.algorithm)
        cmd.append(self.inputs.in_file)

        # Positional output file(s)
        if self.inputs.algorithm == 'dhollander':
            cmd.extend([self.inputs.wm_file, self.inputs.gm_file, self.inputs.csf_file])
        else:
            cmd.append(self.inputs.out_file)

        # Options
        if self.inputs.force:
            cmd.append("-force")
        if self.inputs.nthreads > 1:
            cmd.append(f"-nthreads {self.inputs.nthreads}")
        if isdefined(self.inputs.mask):
            cmd.append(f"-mask {self.inputs.mask}")
        if isdefined(self.inputs.voxels):
            cmd.append(f"-voxels {self.inputs.voxels}")

        return " ".join(cmd)


    def _list_outputs(self):
        outputs = self.output_spec().get()
        if self.inputs.algorithm == 'dhollander':
            if isdefined(self.inputs.wm_file):
                outputs["wm_file"] = os.path.abspath(self.inputs.wm_file)
            else:
                outputs["wm_file"] = os.path.abspath(self._filename_from_source("wm_file"))
            if isdefined(self.inputs.gm_file):
                outputs["gm_file"] = os.path.abspath(self.inputs.gm_file)
            else:
                outputs["gm_file"] = os.path.abspath(self._filename_from_source("gm_file"))
            if isdefined(self.inputs.csf_file):
                outputs["csf_file"] = os.path.abspath(self.inputs.csf_file)
            else:
                outputs["csf_file"] = os.path.abspath(self._filename_from_source("csf_file"))
            # The 'out_file' is not used for dhollander, but Nipype requires it to be defined.
            # We can point it to the wm_file as the primary output.
            outputs["out_file"] = outputs["wm_file"]
        else:
            if isdefined(self.inputs.out_file):
                outputs["out_file"] = os.path.abspath(self.inputs.out_file)
            else:
                outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))

        if isdefined(self.inputs.voxels):
            outputs["voxels"] = os.path.abspath(self.inputs.voxels)

        return outputs
