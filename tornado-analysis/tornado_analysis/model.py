"""Run the market model (standard PyPSA optimisation) and collect metrics."""

import pandas as pd

from .welfare import welfare_by_country


class OptimizationError(RuntimeError):
    """Solve did not end 'ok' (infeasible, unbounded, ...); carries diagnostics."""

    def __init__(self, status, condition, diagnostics):
        self.status = status
        self.condition = condition
        self.diagnostics = diagnostics
        super().__init__(f"optimisation failed: {status} / {condition}")


def diagnose(network, status, condition, solver, error=None):
    """Collect hints on why a solve failed (infeasible / unbounded / other)."""
    d = {"solver": solver.get("name", "highs"), "status": str(status),
         "termination_condition": str(condition)}
    if error is not None:
        d["error"] = f"{type(error).__name__}: {error}"
    cond = str(condition).lower()
    if "infeasible" in cond:
        d["hint"] = ("Infeasible: usually demand cannot be met (capacity cut too deep, p_max_pu too low, "
                     "transmission limits) or conflicting bounds. Consider enabling baseline.load_shedding.")
    elif "unbounded" in cond:
        d["hint"] = ("Unbounded: usually negative marginal/capital costs on uncapped assets, or an "
                     "extendable asset without p_nom_max. A cost perturbation may have flipped a sign.")
    try:
        gens = network.generators
        shed = gens.index.str.endswith(" load shedding")
        demand = network.get_switchable_as_dense("Load", "p_set").sum(axis=1)
        avail = (network.get_switchable_as_dense("Generator", "p_max_pu")[gens.index[~shed]]
                 .mul(gens.loc[~shed, "p_nom"], axis=1).sum(axis=1))
        d["load_shedding_present"] = bool(shed.any())
        d["peak_demand_MW"] = float(demand.max())
        d["min_available_generation_MW"] = float(avail.min())
        d["max_available_generation_MW"] = float(avail.max())
        d["snapshots_with_generation_below_demand"] = int((avail < demand).sum())
        d["negative_marginal_cost_generators"] = gens.index[gens["marginal_cost"] < 0].tolist()
        d["extendable_assets"] = {
            c: int(getattr(network, c)[f"{a}_nom_extendable"].sum())
            for c, a in (("generators", "p"), ("links", "p"), ("storage_units", "p"), ("lines", "s"))
            if f"{a}_nom_extendable" in getattr(network, c).columns
        }
    except Exception as e:  # diagnostics must never mask the original failure
        d["diagnostics_error"] = f"{type(e).__name__}: {e}"
    return d


def run_model(network, solver, prefix_length, voll):
    try:
        status, condition = network.optimize(
            solver_name=solver.get("name", "highs"),
            **({"solver_options": solver["options"]} if solver.get("options") else {}),
        )
    except Exception as e:
        raise OptimizationError("error", "exception", diagnose(network, "error", "exception", solver, e)) from e
    if status != "ok":
        raise OptimizationError(status, condition, diagnose(network, status, condition, solver))

    gens = network.generators
    shed = gens.index[gens.index.str.endswith(" load shedding")]
    real = gens.index.difference(shed)
    available = network.get_switchable_as_dense("Generator", "p_max_pu")[real]
    curtailment = (available.mul(gens.loc[real, "p_nom"], axis=1) - network.generators_t.p[real]).clip(lower=0).sum().sum()

    welfare = welfare_by_country(network, prefix_length=prefix_length, voll=voll)
    return {
        "total_system_cost": float(network.objective),
        "total_generation_MWh": float(network.generators_t.p.sum().sum()),
        "curtailment_MWh": float(curtailment),
        "load_shedding_MWh": float(network.generators_t.p[shed].sum().sum()) if len(shed) else 0.0,
        "avg_electricity_price": float(network.buses_t.marginal_price.mean().mean()),
        "welfare_by_country": welfare.to_dict(orient="index"),
    }
