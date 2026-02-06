from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class ANTsRegistrationInputSpec(CommandLineInputSpec):
    """
    Input Spec for ANTs's antsRegistration command.
    """
    # Required inputs
    fixed_image = File(
        exists=True,
        mandatory=True,
        argstr="--fixed-image %s",
        desc="Fixed image for registration."
    )
    moving_image = File(
        exists=True,
        mandatory=True,
        argstr="--moving-image %s",
        desc="Moving image to be registered."
    )
    output_transform_prefix = traits.Str(
        "transform",
        usedefault=True,
        argstr="--output %s",
        desc="Prefix for output transforms and warped image."
    )
    # Common options
    dimension = traits.Enum(3, 2, argstr="--dimensionality %d", desc="Dimensionality of the input images.")
    
    transform = traits.List(
        traits.Str,
        argstr="%s",
        desc="List of transform stages (e.g., ['Rigid', 'Affine', 'SyN']).",
        sep=" "
    )
    
    # Example simplified transform stage setup
    # A full interface would have separate traits for each stage's parameters
    # For simplicity here, we'll just show the concept
    
    # Note: A proper Nipype interface for antsRegistration is very complex
    # due to the nested structure of transforms. This is a simplified version.
    
    # A more complete interface would look like this:
    # transforms = traits.List(traits.Str, mandatory=True, argstr="%s", desc="List of transforms")
    # transform_parameters = traits.List(traits.List(traits.Float()), argstr="%s", desc="List of transform parameters")
    # metric = traits.List(traits.Str, argstr="%s", desc="List of metrics")
    # metric_weight = traits.List(traits.Float(), argstr="%s", desc="List of metric weights")
    # radius_or_number_of_bins = traits.List(traits.Int(), argstr="%s", desc="List of number of bins")
    # sampling_strategy = traits.List(traits.Enum("Regular", "Random", None), argstr="%s", desc="List of sampling strategies")
    # sampling_percentage = traits.List(traits.Float(), argstr="%s", desc="List of sampling percentages")
    # convergence_threshold = traits.List(traits.Float(), argstr="%s", desc="List of convergence thresholds")
    # convergence_window_size = traits.List(traits.Int(), argstr="%s", desc="List of convergence window sizes")
    # number_of_iterations = traits.List(traits.List(traits.Int()), argstr="%s", desc="List of number of iterations")
    # smoothing_sigmas = traits.List(traits.List(traits.Float()), argstr="%s", desc="List of smoothing sigmas")
    # sigma_units = traits.List(traits.Enum("vox", "mm"), argstr="%s", desc="List of sigma units")
    # shrink_factors = traits.List(traits.List(traits.Int()), argstr="%s", desc="List of shrink factors")
    # use_histogram_matching = traits.List(traits.Bool, argstr="%s", desc="List of use histogram matching")
    
    winsorize_lower_quantile = traits.Float(
        0.005,
        usedefault=True,
        argstr="--winsorize-image-intensities [ %f",
        desc="Winsorize lower quantile."
    )
    winsorize_upper_quantile = traits.Float(
        0.995,
        usedefault=True,
        argstr=", %f ]",
        desc="Winsorize upper quantile."
    )
    
class ANTsRegistrationOutputSpec(TraitedSpec):
    """
    Output Spec for ANTs's antsRegistration command.
    """
    forward_warp_field = File(desc="Forward warp field.")
    inverse_warp_field = File(desc="Inverse warp field.")
    affine_transform = File(desc="Affine transform.")
    warped_image = File(desc="Warped moving image.")

class ANTsRegistration(CommandLine):
    """
    Wraps the ANTs antsRegistration command for image registration.

    This is a simplified interface. For a full implementation, see Nipype's
    `nipype.interfaces.ants.Registration`.
    
    Examples
    --------
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.ants import ANTsRegistration
    >>> Path("fixed.nii.gz").touch()
    >>> Path("moving.nii.gz").touch()
    >>> reg = ANTsRegistration()
    >>> reg.inputs.fixed_image = "fixed.nii.gz"
    >>> reg.inputs.moving_image = "moving.nii.gz"
    >>> reg.inputs.output_transform_prefix = "transform"
    >>> # A simplified example of a transform string
    >>> reg.inputs.transform = ["--transform Rigid[0.1]", "--metric CC[fixed.nii.gz,moving.nii.gz,1,4]", "--convergence [1000x500,1e-6,10]", "--shrink-factors 2x1", "--smoothing-sigmas 1x0vox"]
    >>> reg.cmdline
    'antsRegistration --dimensionality 3 --winsorize-image-intensities [ 0.005000, 0.995000 ] --fixed-image fixed.nii.gz --moving-image moving.nii.gz --output transform --transform Rigid[0.1] --metric CC[fixed.nii.gz,moving.nii.gz,1,4] --convergence [1000x500,1e-6,10] --shrink-factors 2x1 --smoothing-sigmas 1x0vox'
    """
    _cmd = "antsRegistration"
    input_spec = ANTsRegistrationInputSpec
    output_spec = ANTsRegistrationOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        prefix = self.inputs.output_transform_prefix
        # ANTsRegistration creates several files based on the output prefix
        outputs["affine_transform"] = os.path.abspath(f"{prefix}0GenericAffine.mat")
        outputs["forward_warp_field"] = os.path.abspath(f"{prefix}1Warp.nii.gz")
        outputs["inverse_warp_field"] = os.path.abspath(f"{prefix}1InverseWarp.nii.gz")
        outputs["warped_image"] = os.path.abspath(f"{prefix}Warped.nii.gz")
        return outputs
