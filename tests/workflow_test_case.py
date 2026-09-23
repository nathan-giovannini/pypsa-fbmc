"""
Defines FBMCWorkflowTestCase — a dataclass describing a full workflow test scenario —
and run_workflow_test, which executes the scenario and returns the objective value.
"""
from dataclasses import dataclass, field
import pypsa 


from fbmc.enums import BaseCaseStrategy, GSKStrategy
from fbmc.settings import FBMCConfig
from fbmc.types import FBMCResult
from fbmc.workflows.redispatch import run as run_redispatch


@dataclass
class FBMCWorkflowTestCase:
    """Fully describes a single FBMC workflow test scenario."""
    case_name: str
    zonal_net: None | pypsa.Network = None
    nodal_net: None | pypsa.Network = None
    gsk: None | dict = None
    gsk_strategy: GSKStrategy | None = None
    base_case_strategy: BaseCaseStrategy | None = None
    advanced_hybrid_coupling_flag: bool | None = None
    config: FBMCConfig = field(default_factory=FBMCConfig)
    case_kwargs: dict = field(default_factory=dict)
    expected_objective: float | None = None
    expected_rd_objective: float | None = None
    """If set, the test asserts the objective value matches within `tolerance`."""
    tolerance: float = 1e-2
    run_redispatch_flag: bool = True
    redispatch_kwargs: dict = None


def run_workflow_test(
        test_case: FBMCWorkflowTestCase,
) -> tuple[FBMCResult, float]:
    """
    Run the full FBMC (and optionally redispatch) workflow for the given test case.

    Returns the FBMCResult so callers can do additional assertions.
    """
    config = test_case.config
    config.gsk_strategy = test_case.gsk_strategy
    config.base_case_strategy = test_case.base_case_strategy
    config.advanced_hybrid_coupling_flag = test_case.advanced_hybrid_coupling_flag
    test_case.zonal_net.fbmc.create_model(
        test_case.nodal_net,
        config,
        gsk=test_case.gsk,
    )
    test_case.zonal_net.fbmc.solve(**(config.solver_kwargs or {}))
    result = test_case.zonal_net.fbmc.results()

    redispatch_kwargs = test_case.redispatch_kwargs or {}
    if test_case.run_redispatch_flag:
        nodal_net, rd_cost = run_redispatch(
            test_case.nodal_net, result.dispatch_results, **redispatch_kwargs   
        )
    return result, rd_cost if test_case.run_redispatch_flag else None
