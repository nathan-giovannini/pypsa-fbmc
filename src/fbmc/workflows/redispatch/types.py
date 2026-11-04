from dataclasses import dataclass

import pypsa

from fbmc.types import DispatchResult

@dataclass
class RedispatchResult:
    nodal_net: pypsa.Network
    cost: float
    dispatch_results: DispatchResult


ReferenceDispatch = DispatchResult
