import linopy as lp
import pypsa

from fbmc.api import create_model as create_fbmc_model
from fbmc.api import results as collect_fbmc_results
from fbmc.api import run_fbmc, solve as solve_fbmc_model
from fbmc.network.network_conversion import nodal_to_zonal
from fbmc.settings import FBMCConfig
from fbmc.types import FBMCResult


class FBMCAccessor:
    def __init__(self, network: pypsa.Network):
        self._n = network

    def to_zonal(self, bus_zone_mapping, **kwargs) -> pypsa.Network:
        return nodal_to_zonal(self._n, bus_zone_map=bus_zone_mapping, **kwargs)

    def run(self, nodal: pypsa.Network, config: FBMCConfig, gsk=None, cnecs=None) -> FBMCResult:
        return run_fbmc(self._n, nodal, config, gsk=gsk, cnecs=cnecs)

    def create_model(self, nodal: pypsa.Network, config: FBMCConfig, gsk=None, cnecs=None) -> lp.Model:
        return create_fbmc_model(self._n, nodal, config, gsk=gsk, cnecs=cnecs)

    def solve(self, **solver_overrides) -> lp.Model:
        return solve_fbmc_model(self._n, **solver_overrides)

    def results(self) -> FBMCResult:
        return collect_fbmc_results(self._n)


doc = (
    "Accessor for FBMC functionality on pypsa.Network objects. "
    "Use `network.fbmc.to_zonal(bus_zone_mapping)` to create a zonal network, "
    "`zonal_net.fbmc.run(nodal_network, config, ...)` for the recommended one-step workflow, "
    "or `create_model()`, `solve()`, and `results()` for step-by-step inspection."
)

pypsa.Network.fbmc = property(FBMCAccessor, doc=doc)
