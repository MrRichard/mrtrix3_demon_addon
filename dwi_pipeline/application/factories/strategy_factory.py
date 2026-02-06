from typing import Dict, Type

from ...domain.models.bids_layout import BidsLayout
from ...domain.models.processing_config import ProcessingConfig
from ...domain.models.dwi_data import DwiData
from ...domain.enums.shell_type import ShellType
from ...domain.enums.species import Species
from ..strategies.base import ProcessingStrategy
from ..strategies.single_shell import SingleShellStrategy
from ..strategies.multi_shell import MultiShellStrategy

class StrategyFactory:
    """
    Factory for creating the appropriate processing strategy based on data characteristics.
    """
    def __init__(self):
        self._strategies: Dict[tuple[Species, ShellType], Type[ProcessingStrategy]] = {
            (Species.HUMAN, ShellType.SINGLE_SHELL): SingleShellStrategy,
            (Species.HUMAN, ShellType.MULTI_SHELL): MultiShellStrategy,
            # Future strategies can be registered here, e.g., for NHP
            # (Species.NHP, ShellType.SINGLE_SHELL): NhpSingleShellStrategy,
        }

    def create_strategy(
        self,
        layout: BidsLayout,
        config: ProcessingConfig,
        dwi_data: DwiData
    ) -> ProcessingStrategy:
        """
        Selects and instantiates the appropriate processing strategy.

        Args:
            layout (BidsLayout): The BIDS layout of the data.
            config (ProcessingConfig): The processing configuration.
            dwi_data (DwiData): The DWI data with derived metadata.

        Returns:
            An instance of a concrete ProcessingStrategy subclass.

        Raises:
            NotImplementedError: If no strategy is found for the given species and shell type.
        """
        key = (config.species, dwi_data.shell_type)
        strategy_class = self._strategies.get(key)

        if not strategy_class:
            raise NotImplementedError(
                f"No processing strategy found for species '{config.species.value}' "
                f"and shell type '{dwi_data.shell_type.value}'"
            )

        return strategy_class(layout, config, dwi_data)
