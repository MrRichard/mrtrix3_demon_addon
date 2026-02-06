from nipype.pipeline.engine import Workflow

from ...domain.models.bids_layout import BidsLayout
from ...domain.models.processing_config import ProcessingConfig
from ...domain.models.dwi_data import DwiData
from ..factories.strategy_factory import StrategyFactory
from ..builders.workflow_builder import WorkflowBuilder, WorkflowDirector

class WorkflowFactory:
    """
    Factory for creating the entire Nipype workflow for DWI processing.
    
    This factory orchestrates the selection of a processing strategy
    and the construction of the workflow using the Builder pattern.
    """
    def create_workflow(
        self,
        layout: BidsLayout,
        config: ProcessingConfig,
        dwi_data: DwiData
    ) -> Workflow:
        """
        Creates a complete Nipype workflow for a given subject and session.

        Args:
            layout (BidsLayout): The BIDS layout of the data.
            config (ProcessingConfig): The processing configuration.
            dwi_data (DwiData): The DWI data with derived metadata.

        Returns:
            A fully constructed Nipype Workflow object.
        """
        # 1. Select the processing strategy
        strategy_factory = StrategyFactory()
        strategy = strategy_factory.create_strategy(layout, config, dwi_data)

        # 2. Instantiate the builder with the chosen strategy
        builder = WorkflowBuilder(strategy, config, layout, dwi_data)
        
        # 3. Use a director to construct the full pipeline
        #    This encapsulates the specific sequence of building steps.
        director = WorkflowDirector(builder)
        workflow = director.construct_full_pipeline()

        return workflow
