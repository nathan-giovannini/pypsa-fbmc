"""
This is the file you adapt to your actual electricity market model. The
rest of the framework only cares that `run_model(network)` takes a
(possibly perturbed) PyPSA network and returns a dict of metrics for the
tornado analysis -- including, optionally, a "welfare_by_country" entry
(a dict of country -> welfare) used to assess how market welfare
redistributes between countries.
"""

import pypsa

from config import COUNTRY_BUS_PREFIX_LENGTH, VOLL
from welfare import welfare_by_country


def run_model(network: pypsa.Network) -> dict:
    """
    Run the electricity market model on `network` and return a dict of
    output metrics for the tornado analysis.
    """

    # --- Case A: your market model IS PyPSA's own optimizer -------------
    network.optimize(solver_name="gurobi")  # swap solver/options as needed

    total_cost = network.objective
    total_generation = network.generators_t.p.sum().sum()
    curtailment = (
        network.generators_t.p_max_pu.mul(network.generators.p_nom, axis=1)
        - network.generators_t.p
    ).clip(lower=0).sum().sum()
    avg_price = network.buses_t.marginal_price.mean().mean()

    welfare = welfare_by_country(
        network, prefix_length=COUNTRY_BUS_PREFIX_LENGTH, voll=VOLL
    )

    return {
        "total_system_cost": total_cost,
        "total_generation_MWh": total_generation,
        "curtailment_MWh": curtailment,
        "avg_electricity_price": avg_price,
        "welfare_by_country": welfare.to_dict(),
    }

    # --- Case B: an EXTERNAL market model consumes the PyPSA network -----
    # import subprocess
    # network.export_to_netcdf("temp_network.nc")
    # subprocess.run(
    #     ["your_market_model_cli", "--input", "temp_network.nc",
    #      "--output", "temp_results.nc"],
    #     check=True,
    # )
    # results = load_your_results("temp_results.nc")
    # # you'll need marginal prices / dispatch back on `network` (or from
    # # `results`) to compute welfare_by_country -- adapt welfare.py if your
    # # external model returns these differently.
    # return {
    #     "total_system_cost": results.cost,
    #     "welfare_by_country": results.welfare_by_country,
    #     ...
    # }
