"""
This is the file you adapt to your actual electricity market model. The
rest of the framework only cares that `run_model(network)` takes a
(possibly perturbed) PyPSA network and returns a dict of metrics for the
tornado analysis -- including, optionally, a "welfare_by_country" entry
(a dict of country -> welfare) used to assess how market welfare
redistributes between countries.
"""

import pypsa
import xarray as xr

from config import COUNTRY_BUS_PREFIX_LENGTH, VOLL
from welfare import welfare_by_country


def get_prices(zonal_net, nodal_net):
    ## prices per zone from the netposition
    for zone in zonal_net.buses.index.unique():
        zonal_net.buses_t.marginal_price[zone] = (
                zonal_net.model.constraints["Zone-definition"].loc[:, zone].dual.to_pandas() * -1)

    ##prices per zone from the nodal prices
    ### defining buses with nodal prices
    # Assuming your network is called n
    nodal_net.determine_network_topology()
    # Count buses in each subnetwork
    subnet_sizes = nodal_net.buses.groupby("sub_network").size()
    # Subnetworks with fewer than 3 buses
    small_subnets = subnet_sizes[subnet_sizes < 3].index
    # Bus names in those subnetworks
    small_subnet_buses = nodal_net.buses[nodal_net.buses["sub_network"].isin(small_subnets)].index.tolist()
    small_subnet_zones = nodal_net.buses.zone_name.loc[small_subnet_buses].values

    for zone in small_subnet_zones:
        zonal_net.buses_t.marginal_price[zone] = zonal_net.model.constraints["Bus-nodal_balance"].loc[
                                                        zone, :].dual.to_pandas()

    return zonal_net

def get_lines_results(zonal_net, nodal_net, fbmc_parameters, net_positions):
    bus_zone_map = nodal_net.buses['zone_name']

    zonal_net.lines = nodal_net.lines
    zonal_net.lines["zone0"] = zonal_net.lines.bus0.map(bus_zone_map)
    zonal_net.lines["zone1"] = zonal_net.lines.bus1.map(bus_zone_map)

    z_ptdf = xr.concat(
        [ds.z_ptdf for ds in fbmc_parameters.values()],
        dim="cnec"
    )
    zonal_net.lines_t.p0 =    (
            z_ptdf * net_positions
    ).sum(dim="Zone").to_pandas()

    return zonal_net



def run_model(network: pypsa.Network) -> dict:
    """
    Run the electricity market model on `network` and return a dict of
    output metrics for the tornado analysis.
    """

    # --- Case A: your market model IS PyPSA's own optimizer -------------
    # network.optimize(solver_name="gurobi")  # swap solver/options as needed
    #
    # total_cost = network.objective
    # total_generation = network.generators_t.p.sum().sum()
    # curtailment = (
    #     network.generators_t.p_max_pu.mul(network.generators.p_nom, axis=1)
    #     - network.generators_t.p
    # ).clip(lower=0).sum().sum()
    # avg_price = network.buses_t.marginal_price.mean().mean()
    #
    # welfare = welfare_by_country(
    #     network, prefix_length=COUNTRY_BUS_PREFIX_LENGTH, voll=VOLL
    # )
    #
    # return {
    #     "total_system_cost": total_cost,
    #     "total_generation_MWh": total_generation,
    #     "curtailment_MWh": curtailment,
    #     "avg_electricity_price": avg_price,
    #     "welfare_by_country": welfare.to_dict(),
    # }

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

    import fbmc
    nodal_net = network.copy()
    bus_zone_map = nodal_net.buses['zone_name']
    zonal_net = nodal_net.fbmc.to_zonal(bus_zone_map)

    config = fbmc.FBMCConfig(
        base_case_strategy=fbmc.BaseCaseStrategy.NODAL_OPTIMUM,
        add_security_constraints=False,
        gsk_strategy=fbmc.GSKStrategy.P_NOM,
        security_constraint_bodf_size_threshold=0.1,
        solver_kwargs={'solver_name': 'gurobi', 'OutputFlag': 0},
    )

    zonal_net.fbmc.create_model(nodal_net, config=config)
    zonal_net.model.solve(**config.solver_kwargs)
    result = zonal_net.fbmc.results()

    result.zonal_net.buses["country"] = zonal_net.buses.index

    result.zonal_net = get_prices(result.zonal_net, nodal_net)
    result.zonal_net = get_lines_results(result.zonal_net, nodal_net, result.fbmc_parameters, result.net_positions)


    total_cost = result.zonal_net.model.objective.value
    total_generation = result.zonal_net.generators_t.p.sum().sum()
    curtailment = (
        result.zonal_net.generators_t.p_max_pu.mul(result.zonal_net.generators.p_nom, axis=1)
        - result.zonal_net.generators_t.p
    ).clip(lower=0).sum().sum()
    avg_price = result.zonal_net.buses_t.marginal_price.mean().mean()


    welfare_df = welfare_by_country(
        result.zonal_net, prefix_length=COUNTRY_BUS_PREFIX_LENGTH, voll=VOLL
    )
    print(f"welfare_df columns in model_interface {welfare_df.columns}")

    return {
        "total_system_cost": total_cost,
        "total_generation_MWh": total_generation,
        "curtailment_MWh": curtailment,
        "avg_electricity_price": avg_price,
        "welfare_by_country": welfare_df.to_dict(orient="index"),
    }

