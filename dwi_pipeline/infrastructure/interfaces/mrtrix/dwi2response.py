from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class DWI2ResponseInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwi2response command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-3,
        desc="Input DWI image file (MIF format)."
    )
    algorithm = traits.Enum(
        "tournier", "dhollander", "fa", "tax", "manual",
        argstr="%s",
        position=-2,
        desc="Algorithm to use for response function estimation."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_response.txt",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output response function text file."
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
    # Algorithm parameters
    mask = File(
        exists=True,
        argstr="-mask %s",
        desc="Provide a brain mask."
    )
    voxels = File(
        argstr="-voxels %s",
        desc="Output a mask containing the voxels selected by the algorithm."
    )
    # dhollander-specific options
    wm_file = File(
        name_source="in_file",
        name_template="%s_wm_response.txt",
        keep_extension=False,
        argstr="%s",
        desc="White matter response function (dhollander)."
    )
    gm_file = File(
        name_source="in_file",
        name_template="%s_gm_response.txt",
        keep_extension=False,
        argstr="%s",
        desc="Gray matter response function (dhollander)."
    )
    csf_file = File(
        name_source="in_file",
        name_template="%s_csf_response.txt",
        keep_extension=False,
        argstr="%s",
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
    'dwi2response -nthreads 4 -mask mask.mif dwi.mif tournier response.txt'
    >>> # For dhollander
    >>> response.inputs.algorithm = "dhollander"
    >>> response.inputs.wm_file = "wm_response.txt"
    >>> response.inputs.gm_file = "gm_response.txt"
    >>> response.inputs.csf_file = "csf_response.txt"
    >>> response.cmdline
    'dwi2response -nthreads 4 -mask mask.mif dwi.mif dhollander wm_response.txt gm_response.txt csf_response.txt'
    >>> # Run this for real if MRtrix3 is installed and in PATH
    >>> # response.run()
    """
    _cmd = "dwi2response"
    input_spec = DWI2ResponseInputSpec
    output_spec = DWI2ResponseOutputSpec
    
    def _format_arg(self, name, spec, value):
        if name in ['wm_file', 'gm_file', 'csf_file']:
            # The dhollander response files are positional arguments
            # We override the base class _format_arg to place them correctly
            return value
        return super(DWI2Response, self)._format_arg(name, spec, value)

    @property
    def cmdline(self):
        cmd = super(DWI2Response, self).cmdline
        if self.inputs.algorithm == 'dhollander':
            # For dhollander, we need to explicitly list the wm/gm/csf output files
            # in the correct order. The base cmdline generator might not handle this.
            parts = cmd.split()
            # Find the position of the algorithm
            try:
                idx = parts.index('dhollander')
                # Rebuild command ensuring order
                new_cmd = parts[:idx+1] + [self.inputs.wm_file, self.inputs.gm_file, self.inputs.csf_file]
                return ' '.join(new_cmd)
            except ValueError:
                # Should not happen if algorithm is dhollander
                return cmd
        return cmd


    def _list_outputs(self):
        outputs = self.output_spec().get()
        if self.inputs.algorithm == 'dhollander':
            outputs["wm_file"] = os.path.abspath(self.inputs.wm_file)
            outputs["gm_file"] = os.path.abspath(self.inputs.gm_file)
            outputs["csf_file"] = os.path.abspath(self.inputs.csf_file)
            # The 'out_file' is not used for dhollander, but Nipype requires it to be defined.
            # We can point it to the wm_file as the primary output.
            outputs["out_file"] = os.path.abspath(self.inputs.wm_file)
        else:
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        
        if self.inputs.voxels:
            outputs["voxels"] = os.path.abspath(self.inputs.voxels)
            
        return outputs
