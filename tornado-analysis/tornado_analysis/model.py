"""Run the market model (standard PyPSA optimisation) and collect metrics."""

from .welfare import welfare_by_country


def run_model(network, solver, prefix_length, voll):
    status, condition = network.optimize(
        solver_name=solver.get("name", "highs"),
        **({"solver_options": solver["options"]} if solver.get("options") else {}),
    )
    if status != "ok":
        raise RuntimeError(f"optimisation failed: {status} / {condition}")

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
