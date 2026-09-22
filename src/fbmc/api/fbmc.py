from __future__ import annotations

import logging
from collections.abc import Sequence

import linopy as lp
import pypsa

from fbmc.core.inputs.checks import do_input_checks
from fbmc.core.inputs.main import calc_input_parameters
from fbmc.core.model.main import setup_fbmc_model
from fbmc.core.results.extraction import extract_model_results
from fbmc.settings import FBMCConfig
from fbmc.types import DispatchResult, FBMCModelState, FBMCResult

logger = logging.getLogger(__name__)


def _drop_existing_model(network: pypsa.Network) -> None:
    try:
        if hasattr(network, "model"):
            del network.model
    except ValueError:
        pass


def get_fbmc_state(zonal_net: pypsa.Network) -> FBMCModelState:
    state = getattr(zonal_net, "_fbmc_state", None)
    if state is None:
        raise ValueError(
            "No FBMC state is attached to this network. "
            "Call zonal_net.fbmc.run(...) or zonal_net.fbmc.create_model(...) first."
        )
    return state


def create_model(
    zonal_net: pypsa.Network,
    nodal_net: pypsa.Network,
    config: FBMCConfig,
    gsk: dict | None = None,
    cnecs: Sequence[Sequence] | None = None,
) -> lp.Model:
    do_input_checks(nodal_net, zonal_net, gsk, config, cnecs_input=cnecs)
    if nodal_net.sub_networks.empty:
        nodal_net.determine_network_topology()

    input_parameters = calc_input_parameters(
        nodal_net,
        gsk,
        config,
        cnecs_input=cnecs,
    )
    _drop_existing_model(zonal_net)
    model, fbmc_parameters = setup_fbmc_model(
        zonal_net,
        input_parameters=input_parameters,
        config=config,
    )
    zonal_net._fbmc_state = FBMCModelState(
        config=config,
        input_parameters=input_parameters,
        fbmc_parameters=fbmc_parameters,
    )
    return model


def solve(zonal_net: pypsa.Network, **solver_overrides) -> lp.Model:
    state = get_fbmc_state(zonal_net)
    if getattr(zonal_net, "model", None) is None:
        raise ValueError(
            "No FBMC model is attached to this network. "
            "Call zonal_net.fbmc.create_model(...) first."
        )

    solver_kwargs = dict(state.config.solver_kwargs or {})
    solver_kwargs.update(solver_overrides)
    logger.info("Solving FBMC model.")
    zonal_net.model.solve(**solver_kwargs)
    state.solved = zonal_net.model.termination_condition == "optimal"
    state.result = None
    if not state.solved:
        raise ValueError("FBMC optimization did not solve to optimality.")
    return zonal_net.model


def results(zonal_net: pypsa.Network) -> FBMCResult:
    state = get_fbmc_state(zonal_net)
    if getattr(zonal_net, "model", None) is None:
        raise ValueError(
            "No FBMC model is attached to this network. "
            "Call zonal_net.fbmc.create_model(...) first."
        )
    if zonal_net.model.termination_condition != "optimal":
        raise ValueError(
            "FBMC optimization did not solve to optimality. "
            "Call zonal_net.fbmc.solve() before requesting results."
        )
    if state.result is None:
        extract_model_results(zonal_net)
        state.result = FBMCResult(
            zonal_net=zonal_net,
            net_positions=zonal_net.model.solution["Zone-p"],
            dispatch_results=DispatchResult(zonal_net),
            fbmc_parameters=state.fbmc_parameters,
            base_case=state.base_case,
        )
        state.solved = True
    return state.result


def run_fbmc(
    zonal_net: pypsa.Network,
    nodal_net: pypsa.Network,
    config: FBMCConfig,
    gsk: dict | None = None,
    cnecs: Sequence[Sequence] | None = None,
) -> FBMCResult:
    create_model(
        zonal_net=zonal_net,
        nodal_net=nodal_net,
        config=config,
        gsk=gsk,
        cnecs=cnecs,
    )
    solve(zonal_net)
    return results(zonal_net)
