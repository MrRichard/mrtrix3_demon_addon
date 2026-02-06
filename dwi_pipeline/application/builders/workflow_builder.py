from __future__ import annotations
from typing import Dict
import logging

from nipype.pipeline.engine import Workflow, Node
from nipype.interfaces import utility as niu

from ...domain.models import ProcessingConfig, BidsLayout, DwiData
from ...domain.enums import DistortionStrategy
from ...application.strategies import ProcessingStrategy, SingleShellStrategy, MultiShellStrategy
from ...infrastructure.interfaces import mrtrix as mrtrix_interfaces, fsl as fsl_interfaces
from ...infrastructure.interfaces.mrtrix import (
    MRConvert, DWIDenoise, MRDeGibbs, DWIFslPreproc, DWIBiasCorrect, DWI2Mask,
    DWIExtract, TT5Gen, TT5ToGMWMI, TCKGen, TckSift2, TCK2Connectome
)

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
                ('in_bval', 'fslgrad.0'),
                ('in_bvec', 'fslgrad.1'),
                ('in_json', 'json_sidecar')
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

    def add_tractography(self) -> WorkflowBuilder:
        """Adds tractography and connectome generation nodes."""
        logger.info("Adding tractography and connectome generation nodes...")
        
        extract_b0 = Node(DWIExtract(bzero=True, out_file="b0.mif"), name="extract_b0")
        self.workflow.connect([(self.nodes['biascorrect'], extract_b0, [('out_file', 'in_file')])])

        bet_t1w = Node(fsl_interfaces.Bet(mask=True, robust=True), name="bet_t1w")
        self.workflow.connect([(self.nodes['inputspec'], bet_t1w, [('t1w_file', 'in_file')])])
        
        flirt = Node(fsl_interfaces.Flirt(dof=6, cost="mutualinfo"), name="flirt_t1_to_dwi")
        self.workflow.connect([
            (bet_t1w, flirt, [('out_file', 'in_file')]),
            (extract_b0, flirt, [('out_file', 'reference')])
        ])

        tt5gen = Node(TT5Gen(
            algorithm='fsl',
            force=True,
            nthreads=self.config.n_threads
        ), name='5ttgen')
        self.workflow.connect([(flirt, tt5gen, [('out_file', 'in_file')])])

        tt5_to_gmwmi = Node(TT5ToGMWMI(force=True), name='5tt2gmwmi')
        self.workflow.connect([(tt5gen, tt5_to_gmwmi, [('out_file', 'in_file')])])

        tckgen = Node(TCKGen(
            algorithm='iFOD2',
            select=10000000,
            backtrack=True,
            crop_at_gmwmi=True,
            force=True,
            nthreads=self.config.n_threads,
            cutoff=self.strategy.get_fod_cutoff()
        ), name='tckgen')
        
        fod_node_name = "dwi2fod_csd" if isinstance(self.strategy, SingleShellStrategy) else "dwi2fod_msmt"
        fod_output_name = "out_file" if isinstance(self.strategy, SingleShellStrategy) else "wm_odf"
        
        self.workflow.connect([
            (self.nodes[fod_node_name], tckgen, [(fod_output_name, 'in_file')]),
            (tt5gen, tckgen, [('out_file', 'act')]),
            (tt5_to_gmwmi, tckgen, [('out_file', 'seed_gmwmi')])
        ])

        tcksift2 = Node(TckSift2(
            term_number=1000000,
            force=True,
            nthreads=self.config.n_threads
        ), name='tcksift2')
        self.workflow.connect([
            (tckgen, tcksift2, [('out_file', 'in_tracks')]),
            (self.nodes[fod_node_name], tcksift2, [(fod_output_name, 'in_fod')]),
            (tt5gen, tcksift2, [('out_file', 'act')])
        ])
        
        tck2connectome_fs = Node(TCK2Connectome(
            symmetric=True,
            zero_diagonal=True,
            stat_edge="count",
            force=True,
            nthreads=self.config.n_threads
        ), name='tck2connectome_fs')
        
        self.workflow.connect([
            (tckgen, tck2connectome_fs, [('out_file', 'in_file')]),
            (tcksift2, tck2connectome_fs, [('out_weights', 'in_weights')])
        ])

        logger.info("Tractography and connectome nodes added.")
        return self

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
                .add_tractography()
                .build())