from __future__ import annotations
from typing import Dict
import logging

from nipype.pipeline.engine import Workflow, Node
from nipype.interfaces import utility as niu
from nipype.interfaces.io import DataSink

from ...domain.models import ProcessingConfig, BidsLayout, DwiData
from ...domain.enums import DistortionStrategy
from ...application.strategies import ProcessingStrategy, SingleShellStrategy, MultiShellStrategy
from ...infrastructure.interfaces.mrtrix import (
    MRConvert, DWIDenoise, MRDeGibbs, DWIFslPreproc, DWIBiasCorrect, DWI2Mask,
    DWIExtract, TT5Gen, TT5ToGMWMI, TCKGen, TckSift2, TCK2Connectome,
    MtNormalise, LabelConvert
)
from ...infrastructure.interfaces.fsl import Bet, Flirt
from ...utils.constants import find_mrtrix_lut_dir, find_freesurfer_color_lut, FS_DEFAULT_LUT, FS_A2009S_LUT

logger = logging.getLogger(__name__)


class WorkflowBuilder:
    """
    Implements the Builder pattern to construct complex Nipype workflows
    in a step-by-step manner.
    """
    def __init__(
        self,
        strategy: ProcessingStrategy,
        config: ProcessingConfig,
        layout: BidsLayout,
        dwi_data: DwiData
    ):
        self.strategy = strategy
        self.config = config
        self.layout = layout
        self.dwi_data = dwi_data
        self.workflow: Workflow | None = None
        self.nodes: Dict[str, Node] = {}
        self._reset()

    def _reset(self) -> None:
        """Resets the builder, creating a new empty workflow."""
        self.workflow = Workflow(
            name=f"{self.config.run_id}_dwi_pipeline",
            base_dir=str(self.config.nipype_work_dir)
        )
        self.nodes = {}
        logger.info(f"Initialized new workflow: {self.workflow.name}")

    def add_preprocessing(self) -> WorkflowBuilder:
        """Adds DWI preprocessing nodes to the workflow."""
        logger.info("Adding preprocessing nodes...")

        input_node = Node(
            niu.IdentityInterface(fields=['dwi_file', 'in_bval', 'in_bvec', 'in_json', 't1w_file']),
            name='inputspec'
        )
        input_node.inputs.dwi_file = str(self.layout.dwi_ap)
        input_node.inputs.in_bval = str(self.layout.dwi_ap_bval)
        input_node.inputs.in_bvec = str(self.layout.dwi_ap_bvec)
        input_node.inputs.in_json = str(self.layout.dwi_ap_json)
        input_node.inputs.t1w_file = str(self.layout.t1w)
        self.nodes['inputspec'] = input_node

        mrconvert = Node(MRConvert(
            force=True,
            nthreads=self.config.n_threads
        ), name='mrconvert')
        self.workflow.connect([
            (input_node, mrconvert, [
                ('dwi_file', 'in_file'),
                ('in_bvec', 'in_bvec'),
                ('in_bval', 'in_bval'),
            ])
        ])

        denoise = Node(DWIDenoise(
            force=True,
            nthreads=self.config.n_threads
        ), name='denoise')
        self.workflow.connect([(mrconvert, denoise, [('out_file', 'in_file')])])

        prev_node = denoise
        if self.strategy.should_apply_degibbs():
            logger.info("Adding Gibbs ringing removal (mrdegibbs).")
            degibbs = Node(MRDeGibbs(
                force=True,
                nthreads=self.config.n_threads
            ), name='degibbs')
            self.workflow.connect([(denoise, degibbs, [('out_file', 'in_file')])])
            prev_node = degibbs
        else:
            logger.info("Skipping Gibbs ringing removal.")

        preproc = self._create_distortion_correction_node()
        self.workflow.connect([(prev_node, preproc, [('out_file', 'in_file')])])

        biascorrect = Node(DWIBiasCorrect(
            use_ants=True,
            force=True,
            nthreads=self.config.n_threads
        ), name='biascorrect')
        self.workflow.connect([(preproc, biascorrect, [('out_file', 'in_file')])])

        mask = Node(DWI2Mask(
            force=True,
            nthreads=self.config.n_threads
        ), name='mask')
        self.workflow.connect([(biascorrect, mask, [('out_file', 'in_file')])])

        self.nodes['biascorrect'] = biascorrect
        self.nodes['mask'] = mask

        logger.info("Preprocessing nodes added.")
        return self

    def _create_distortion_correction_node(self) -> Node:
        """Creates the appropriate distortion correction node."""
        strategy = self.layout.distortion_correction

        preproc = Node(DWIFslPreproc(
            pe_dir=self.dwi_data.pe_direction,
            readout_time=self.dwi_data.total_readout_time,
            force=True,
            nthreads=self.config.n_threads
        ), name='dwifslpreproc')

        if strategy == DistortionStrategy.RPE_PAIR:
            logger.info("Configuring dwifslpreproc for RPE_PAIR (topup/eddy).")
            preproc.inputs.rpe_option = "pair"
        elif strategy == DistortionStrategy.FIELDMAP:
            logger.info("Configuring dwifslpreproc for FIELDMAP.")
            preproc.inputs.rpe_option = "se_epi"
        else: # NONE
            logger.warning("No distortion correction method specified. Using eddy only.")
            preproc.inputs.rpe_option = "none"

        return preproc

    def add_response_estimation(self) -> WorkflowBuilder:
        """Adds response function estimation nodes."""
        logger.info("Adding response function estimation nodes...")
        response_nodes = self.strategy.create_response_nodes()

        for node in response_nodes:
            node.inputs.force = True
            node.inputs.nthreads = self.config.n_threads
            self.workflow.add_nodes([node])
            self.workflow.connect([
                (self.nodes['biascorrect'], node, [('out_file', 'in_file')]),
                (self.nodes['mask'], node, [('out_file', 'mask')])
            ])
            self.nodes[node.name] = node

        logger.info("Response estimation nodes added.")
        return self

    def add_fod_estimation(self) -> WorkflowBuilder:
        """Adds FOD estimation nodes."""
        logger.info("Adding FOD estimation nodes...")
        fod_nodes = self.strategy.create_fod_nodes()

        fod_node = fod_nodes[0]
        fod_node.inputs.force = True
        fod_node.inputs.nthreads = self.config.n_threads
        self.workflow.add_nodes([fod_node])

        self.workflow.connect([
            (self.nodes['biascorrect'], fod_node, [('out_file', 'in_file')]),
            (self.nodes['mask'], fod_node, [('out_file', 'mask')])
        ])

        if isinstance(self.strategy, SingleShellStrategy):
            response_node = self.nodes.get("dwi2response_tournier")
            if response_node:
                self.workflow.connect([(response_node, fod_node, [('out_file', 'response')])])
        elif isinstance(self.strategy, MultiShellStrategy):
            response_node = self.nodes.get("dwi2response_dhollander")
            if response_node:
                self.workflow.connect([
                    (response_node, fod_node, [('wm_file', 'wm_response')]),
                    (response_node, fod_node, [('gm_file', 'gm_response')]),
                    (response_node, fod_node, [('csf_file', 'csf_response')])
                ])

        self.nodes[fod_node.name] = fod_node
        logger.info("FOD estimation nodes added.")
        return self

    def add_normalisation(self) -> WorkflowBuilder:
        """Adds FOD intensity normalisation (mtnormalise) between FOD and tractography."""
        logger.info("Adding mtnormalise node...")

        mtnorm = Node(MtNormalise(
            force=True,
            nthreads=self.config.n_threads
        ), name='mtnormalise')

        if isinstance(self.strategy, SingleShellStrategy):
            fod_node = self.nodes['dwi2fod_csd']
            self.workflow.connect([
                (fod_node, mtnorm, [('out_file', 'in_wm')]),
                (self.nodes['mask'], mtnorm, [('out_file', 'mask')])
            ])
        elif isinstance(self.strategy, MultiShellStrategy):
            fod_node = self.nodes['dwi2fod_msmt']
            self.workflow.connect([
                (fod_node, mtnorm, [('wm_odf', 'in_wm')]),
                (fod_node, mtnorm, [('gm_odf', 'in_gm')]),
                (fod_node, mtnorm, [('csf_odf', 'in_csf')]),
                (self.nodes['mask'], mtnorm, [('out_file', 'mask')])
            ])

        self.nodes['mtnormalise'] = mtnorm
        logger.info("mtnormalise node added.")
        return self

    def add_tractography(self) -> WorkflowBuilder:
        """Adds tractography, parcellation, and connectome generation nodes."""
        logger.info("Adding tractography and connectome generation nodes...")

        # --- Anatomical registration: FS brain.mgz → DWI space ---
        # Convert FreeSurfer brain.mgz to NIfTI
        fs_brain_convert = Node(MRConvert(
            in_file=str(self.layout.fs_brain),
            out_file="brain.nii.gz",
            force=True,
            nthreads=self.config.n_threads
        ), name='fs_brain_convert')
        self.workflow.add_nodes([fs_brain_convert])

        # Extract b0 from preprocessed DWI
        extract_b0 = Node(DWIExtract(bzero=True, out_file="b0.mif"), name="extract_b0")
        self.workflow.connect([(self.nodes['biascorrect'], extract_b0, [('out_file', 'in_file')])])

        # Register FS brain → DWI space (brain.mgz is already skull-stripped)
        flirt_brain = Node(Flirt(
            dof=6,
            cost="mutualinfo",
            out_file="brain_in_dwi.nii.gz",
            out_matrix_file="brain_to_dwi.mat"
        ), name="flirt_brain_to_dwi")
        self.workflow.connect([
            (fs_brain_convert, flirt_brain, [('out_file', 'in_file')]),
            (extract_b0, flirt_brain, [('out_file', 'reference')])
        ])
        self.nodes['flirt_brain_to_dwi'] = flirt_brain

        # 5ttgen on registered brain (already skull-stripped → -premasked)
        tt5gen = Node(TT5Gen(
            algorithm='fsl',
            premasked=True,
            force=True,
            nthreads=self.config.n_threads
        ), name='5ttgen')
        self.workflow.connect([(flirt_brain, tt5gen, [('out_file', 'in_file')])])

        tt5_to_gmwmi = Node(TT5ToGMWMI(force=True), name='5tt2gmwmi')
        self.workflow.connect([(tt5gen, tt5_to_gmwmi, [('out_file', 'in_file')])])

        # --- Tractography using normalised FOD ---
        tckgen = Node(TCKGen(
            algorithm='iFOD2',
            select=10000000,
            backtrack=True,
            crop_at_gmwmi=True,
            force=True,
            nthreads=self.config.n_threads,
            cutoff=self.strategy.get_fod_cutoff()
        ), name='tckgen')

        # Use mtnormalise output for tractography
        self.workflow.connect([
            (self.nodes['mtnormalise'], tckgen, [('out_wm', 'in_file')]),
            (tt5gen, tckgen, [('out_file', 'act')]),
            (tt5_to_gmwmi, tckgen, [('out_file', 'seed_gmwmi')])
        ])

        # SIFT2 filtering — also uses normalised FOD
        tcksift2 = Node(TckSift2(
            term_number=1000000,
            force=True,
            nthreads=self.config.n_threads
        ), name='tcksift2')
        self.workflow.connect([
            (tckgen, tcksift2, [('out_file', 'in_tracks')]),
            (self.nodes['mtnormalise'], tcksift2, [('out_wm', 'in_fod')]),
            (tt5gen, tcksift2, [('out_file', 'act')])
        ])

        # --- Parcellation: FreeSurfer DK atlas ---
        self._add_parcellation_pipeline(
            atlas_name="dk",
            aparc_file=self.layout.fs_aparc_aseg,
            lut_file=FS_DEFAULT_LUT,
            connectome_name="connectome_FreeSurferDK.csv",
            tckgen_node=tckgen,
            tcksift2_node=tcksift2,
            extract_b0_node=extract_b0
        )

        # --- Parcellation: FreeSurfer Destrieux atlas ---
        if self.layout.fs_aparc_destrieux is not None:
            self._add_parcellation_pipeline(
                atlas_name="destrieux",
                aparc_file=self.layout.fs_aparc_destrieux,
                lut_file=FS_A2009S_LUT,
                connectome_name="connectome_Destrieux.csv",
                tckgen_node=tckgen,
                tcksift2_node=tcksift2,
                extract_b0_node=extract_b0
            )
        else:
            logger.warning("Skipping Destrieux atlas — aparc.a2009s+aseg.mgz not found.")

        # TODO: Brainnetome atlas support — requires MNI template + ANTs registration
        # to warp atlas from MNI space to native DWI space.

        # --- DataSink to collect outputs ---
        datasink = Node(DataSink(
            base_directory=str(self.config.output_dir),
            container=f"sub-{self.config.subject}_ses-{self.config.session}" if self.config.session else f"sub-{self.config.subject}"
        ), name='datasink')
        # Disable substitutions — we control file names explicitly
        datasink.inputs.substitutions = []

        # Sink connectomes
        tck2conn_dk = self.nodes.get('tck2connectome_dk')
        if tck2conn_dk:
            self.workflow.connect([(tck2conn_dk, datasink, [('out_file', '@connectome_dk')])])
        tck2conn_dest = self.nodes.get('tck2connectome_destrieux')
        if tck2conn_dest:
            self.workflow.connect([(tck2conn_dest, datasink, [('out_file', '@connectome_destrieux')])])

        # Sink normalised WM FOD
        self.workflow.connect([
            (self.nodes['mtnormalise'], datasink, [('out_wm', '@wmfod_norm')]),
            (self.nodes['mask'], datasink, [('out_file', '@brain_mask')]),
            (tcksift2, datasink, [('out_weights', '@sift2_weights')])
        ])

        logger.info("Tractography and connectome nodes added.")
        return self

    def _add_parcellation_pipeline(
        self,
        atlas_name: str,
        aparc_file,
        lut_file: str,
        connectome_name: str,
        tckgen_node: Node,
        tcksift2_node: Node,
        extract_b0_node: Node
    ) -> None:
        """Adds parcellation conversion, registration, and connectome nodes for one atlas."""
        lut_dir = find_mrtrix_lut_dir()
        fs_color_lut = str(find_freesurfer_color_lut(self.config.freesurfer_dir))
        target_lut = str(lut_dir / lut_file)

        # 1. Convert aparc+aseg.mgz → NIfTI (preserve integer labels)
        parc_convert = Node(MRConvert(
            in_file=str(aparc_file),
            out_file=f"aparc_{atlas_name}.nii.gz",
            datatype="int32",
            force=True,
            nthreads=self.config.n_threads
        ), name=f'parc_convert_{atlas_name}')
        self.workflow.add_nodes([parc_convert])

        # 2. labelconvert: FS label indices → sequential indices
        labelconv = Node(LabelConvert(
            in_lut=fs_color_lut,
            out_lut=target_lut,
            out_file=f"parcels_{atlas_name}.mif",
            force=True,
            nthreads=self.config.n_threads
        ), name=f'labelconvert_{atlas_name}')
        self.workflow.connect([
            (parc_convert, labelconv, [('out_file', 'in_file')])
        ])

        # 3. FLIRT -applyxfm: Transform parcellation to DWI space (nearest neighbour)
        flirt_parc = Node(Flirt(
            apply_xfm=True,
            interp="nearestneighbour",
            out_file=f"parcels_{atlas_name}_in_dwi.nii.gz",
        ), name=f'flirt_parc_{atlas_name}')
        self.workflow.connect([
            (labelconv, flirt_parc, [('out_file', 'in_file')]),
            (extract_b0_node, flirt_parc, [('out_file', 'reference')]),
            (self.nodes['flirt_brain_to_dwi'], flirt_parc, [('out_matrix_file', 'init')])
        ])

        # 4. tck2connectome with this parcellation
        tck2conn = Node(TCK2Connectome(
            symmetric=True,
            zero_diagonal=True,
            stat_edge="count",
            out_file=connectome_name,
            force=True,
            nthreads=self.config.n_threads
        ), name=f'tck2connectome_{atlas_name}')
        self.workflow.connect([
            (tckgen_node, tck2conn, [('out_file', 'in_file')]),
            (tcksift2_node, tck2conn, [('out_weights', 'in_weights')]),
            (flirt_parc, tck2conn, [('out_file', 'in_parc')])
        ])

        self.nodes[f'tck2connectome_{atlas_name}'] = tck2conn

    def build(self) -> Workflow:
        """Returns the constructed workflow."""
        if not self.workflow:
            raise ValueError("Workflow has not been initialized.")
        logger.info("Workflow build complete.")
        return self.workflow


class WorkflowDirector:
    """
    Directs the construction of the workflow using a builder.
    """
    def __init__(self, builder: WorkflowBuilder):
        self.builder = builder

    def construct_full_pipeline(self) -> Workflow:
        """Constructs the full DWI processing pipeline."""
        logger.info("Directing construction of the full pipeline.")
        return (self.builder
                .add_preprocessing()
                .add_response_estimation()
                .add_fod_estimation()
                .add_normalisation()
                .add_tractography()
                .build())
