from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits, isdefined
import os

class DWIFslPreprocInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 dwifslpreproc command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input DWI image file (MIF format)."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_preproc.mif",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output preprocessed DWI image file."
    )
    rpe_option = traits.Enum(
        "none", "pair", "all", "header",
        argstr="-rpe_%s",
        desc="Reverse Phase-Encoding option."
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
    # Alignment and processing options
    align_seepi = traits.Bool(
        False,
        argstr="-align_seepi",
        desc="Align the b=0 images from the spin-echo EPI images to the DWI b=0 images before running topup."
    )
    eddy_options = traits.Str(
        argstr="-eddy_options '%s'",
        desc="Additional options to pass to FSL's eddy command."
    )
    # Distortion correction parameters
    pe_dir = traits.Str(
        mandatory=True,
        argstr="-pe_dir %s",
        desc="Phase encoding direction (e.g., 'j-', 'AP')."
    )
    readout_time = traits.Float(
        mandatory=True,
        argstr="-readout_time %f",
        desc="Total readout time of the EPI sequence."
    )
    # Fieldmap correction parameters
    se_epi = File(
        exists=True,
        argstr="-se_epi %s",
        desc="Spin-echo EPI image for distortion correction."
    )
    topup_options = traits.Str(
        argstr="-topup_options '%s'",
        desc="Additional options to pass to FSL's topup command."
    )

class DWIFslPreprocOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 dwifslpreproc command.
    """
    out_file = File(
        exists=True,
        desc="Preprocessed DWI image file."
    )

class DWIFslPreproc(CommandLine):
    """
    Performs FSL's eddy and topup for DWI preprocessing.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import DWIFslPreproc
    >>> # Create dummy files for demonstration
    >>> Path("dwi.mif").touch()
    >>> preproc = DWIFslPreproc()
    >>> preproc.inputs.in_file = "dwi.mif"
    >>> preproc.inputs.out_file = "dwi_preproc.mif"
    >>> preproc.inputs.rpe_option = "none"
    >>> preproc.inputs.pe_dir = "j-"
    >>> preproc.inputs.readout_time = 0.05
    >>> preproc.inputs.nthreads = 8
    >>> preproc.cmdline
    'dwifslpreproc dwi.mif dwi_preproc.mif -rpe_none -pe_dir j- -readout_time 0.050000 -nthreads 8'
    >>> # Run this for real if MRtrix3 and FSL are installed and in PATH
    >>> # preproc.run()
    """
    _cmd = "dwifslpreproc"
    input_spec = DWIFslPreprocInputSpec
    output_spec = DWIFslPreprocOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.out_file):
            outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        else:
            outputs["out_file"] = os.path.abspath(self._filename_from_source("out_file"))
        return outputs
