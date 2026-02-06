from nipype.interfaces.base import CommandLineInputSpec, CommandLine, File, TraitedSpec, traits
import os

class TCK2ConnectomeInputSpec(CommandLineInputSpec):
    """
    Input Spec for MRtrix3 tck2connectome command.
    """
    in_file = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-3,
        desc="Input tractography file (.tck)."
    )
    in_parc = File(
        exists=True,
        mandatory=True,
        argstr="%s",
        position=-2,
        desc="Input parcellation image file."
    )
    out_file = File(
        name_source="in_file",
        name_template="%s_connectome.csv",
        keep_extension=False,
        position=-1,
        argstr="%s",
        desc="Output connectome file (.csv)."
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
    # SIFT2 weights
    in_weights = File(
        exists=True,
        argstr="-tck_weights_in %s",
        desc="Specify a text scalar file containing the streamline weights (e.g. from tcksift2)."
    )
    # Connectome generation options
    symmetric = traits.Bool(
        False,
        argstr="-symmetric",
        desc="Make the output matrix symmetric."
    )
    zero_diagonal = traits.Bool(
        False,
        argstr="-zero_diagonal",
        desc="Set the diagonal of the matrix to zero."
    )
    stat_edge = traits.Enum(
        "count", "mean_length", "invlength_invnodevolume",
        argstr="-stat_edge %s",
        desc="Statistic to compute for each edge."
    )
    scale_invnodevol = traits.Bool(
        False,
        argstr="-scale_invnodevol",
        desc="Scale edge weights by the inverse of the two node volumes."
    )
    out_assignments = File(
        argstr="-out_assignments %s",
        desc="Output a text file indicating the node assignments for each streamline."
    )

class TCK2ConnectomeOutputSpec(TraitedSpec):
    """
    Output Spec for MRtrix3 tck2connectome command.
    """
    out_file = File(
        exists=True,
        desc="Output connectome file (.csv)."
    )
    out_assignments = File(
        desc="Streamline-node assignments file."
    )

class TCK2Connectome(CommandLine):
    """
    Generates a connectome matrix from a tractogram and a parcellation image.

    Examples
    --------
    >>> import os
    >>> from pathlib import Path
    >>> from dwi_pipeline.infrastructure.interfaces.mrtrix import TCK2Connectome
    >>> Path("tracts.tck").touch()
    >>> Path("parc.mif").touch()
    >>> connectome = TCK2Connectome()
    >>> connectome.inputs.in_file = "tracts.tck"
    >>> connectome.inputs.in_parc = "parc.mif"
    >>> connectome.inputs.out_file = "connectome.csv"
    >>> connectome.inputs.symmetric = True
    >>> connectome.inputs.zero_diagonal = True
    >>> connectome.inputs.stat_edge = "count"
    >>> connectome.inputs.nthreads = 8
    >>> connectome.cmdline
    'tck2connectome -nthreads 8 -symmetric -zero_diagonal -stat_edge count tracts.tck parc.mif connectome.csv'
    """
    _cmd = "tck2connectome"
    input_spec = TCK2ConnectomeInputSpec
    output_spec = TCK2ConnectomeOutputSpec

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        if self.inputs.out_assignments:
            outputs["out_assignments"] = os.path.abspath(self.inputs.out_assignments)
        return outputs
