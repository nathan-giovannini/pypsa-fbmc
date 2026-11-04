"""Flow-Based Market Coupling (FBMC) extension for PyPSA."""

from . import accessor as accessor  # registers pypsa.Network.fbmc on import
from . import api as api
from .api.fbmc import create_model, results, run_fbmc, solve
from .enums import CNECStrategy as CNECStrategy
from .enums import BaseCaseStrategy as BaseCaseStrategy
from .enums import GSKStrategy as GSKStrategy
from .network.network_conversion import nodal_to_zonal
from .settings import FBMCConfig as FBMCConfig
from .settings import merge_config_overrides
from .types import DispatchResult, FBMCResult
from .workflows import redispatch

__all__ = [
    "run_fbmc",
    "create_model",
    "solve",
    "results",
    "api",
    "FBMCConfig",
    "merge_config_overrides",
    "GSKStrategy",
    "BaseCaseStrategy",
    "CNECStrategy",
    "FBMCResult",
    "DispatchResult",
    "nodal_to_zonal",
    "redispatch",
]
