"""Contains the methods for preparing the base case for the FBMC optimization."""
import pypsa


from ..parameters.bridge_branches import find_bridges_network
from ...enums import BaseCaseStrategy


def prepare_nodal_optimum_base_case(_nodal_net: pypsa.Network, solver_kwargs: dict | None = None):
    """Prepare base case using nodal optimziation without security constraints.
    """
    solver_kwargs = solver_kwargs or {}
    base_case = _nodal_net.copy()
    base_case.optimize(**solver_kwargs)
    if base_case.model.termination_condition != 'optimal':
        raise ValueError("Initial nodal optimization did not solve to optimality. Consider adding load shedding at each bus")
    return base_case


def prepare_zero_flow_base_case(_nodal_net: pypsa.Network, solver_kwargs: dict | None = None):
    base_case = _nodal_net.copy()
    base_case.lines_t.p0.loc[base_case.snapshots, base_case.lines.index] = 0
    base_case.transformers_t.p0.loc[base_case.snapshots, base_case.transformers.index] = 0
    base_case.buses_t.p.loc[base_case.snapshots, base_case.buses.index] = 0
    return base_case


def prepare_custom_base_case(_nodal_net: pypsa.Network, solver_kwargs: dict | None = None):
    return _nodal_net.copy()


def prepare_security_constrained_base_case(_nodal_net: pypsa.Network, solver_kwargs: dict | None = None):
    solver_kwargs = solver_kwargs or {}
    base_case = _nodal_net.copy()
    if base_case.sub_networks.empty:
        base_case.determine_network_topology()
    bridges = find_bridges_network(base_case)
    bridge_index = bridges.coords["branch"].to_index()
    line_bridges = bridge_index[bridge_index.get_level_values(0) == "Line"].get_level_values(1)
    branch_outages = base_case.lines.index.difference(line_bridges)
    base_case.optimize.optimize_security_constrained(branch_outages=branch_outages, **solver_kwargs)
    if base_case.model.termination_condition != 'optimal':
        raise ValueError("Initial nodal optimization did not solve to optimality. Consider adding load shedding at each bus with a sufficiently high marginal cost.")
    return base_case


prepare_basecase_fn_mapping = {
    BaseCaseStrategy.ZERO_FLOWS: prepare_zero_flow_base_case,
    BaseCaseStrategy.NODAL_OPTIMUM: prepare_nodal_optimum_base_case,
    BaseCaseStrategy.SECURITY_CONSTRAINED_NODAL_OPTIMUM: prepare_security_constrained_base_case,
    BaseCaseStrategy.CUSTOM: prepare_custom_base_case
}

def prepare_base_case(
    net: pypsa.Network,
    strategy: BaseCaseStrategy,
    solver_kwargs: dict | None = None,
):
    if strategy not in prepare_basecase_fn_mapping:
        raise ValueError(f"Strategy {strategy} is not supported.")
    return prepare_basecase_fn_mapping[strategy](net, solver_kwargs=solver_kwargs)
