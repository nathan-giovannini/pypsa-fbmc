import pandas as pd
from itertools import product
import xarray as xr 

from fbmc.core.parameters.bridge_branches import find_bridges_sub_network

def add_security_constraints(nodal_net, branch_outages):
        if nodal_net.model is None:
             nodal_net.optimize.create_model()
        m = nodal_net.model
        for sub_network in nodal_net.sub_networks.obj:
            branches_i = sub_network.branches_i()
            if branch_outages is None:
                bridges = find_bridges_sub_network(sub_network)
                bridge_index = pd.MultiIndex.from_arrays(
                    [
                        bridges.coords["branch_component"].values,
                        bridges.coords["branch"].values,
                    ]
                )
                outages = branches_i.difference(bridge_index)
            else:
                outages = branches_i.intersection(branch_outages)

            if outages.empty:
                continue
            sub_network.calculate_BODF()
            BODF = pd.DataFrame(sub_network.BODF, index=branches_i, columns=branches_i)[
                outages
            ]

            for outage_component, outage_branch in outages:
                c_outage_ = f"{outage_component}-outage"
                flow_outage = m.variables[f"{outage_component}-s"].loc[:, [outage_branch]]
                flow_outage = flow_outage.rename({outage_component: c_outage_})

                for c_affected in branches_i.unique(0):
                    bodf_series = BODF.loc[c_affected, (outage_component, outage_branch)]
                    bodf = xr.DataArray(
                        bodf_series.values,
                        coords={c_affected: bodf_series.index},
                        dims=[c_affected],
                    )
                    additional_flow = flow_outage * bodf
                    for bound, kind in product(("lower", "upper"), ("fix", "ext")):
                        coord = c_affected + "-" + kind
                        constraint = coord + "-s-" + bound
                        if constraint not in m.constraints:
                            continue
                        rename = {c_affected: coord}
                        added_flow = additional_flow.rename(rename)
                        con = m.constraints[constraint]  # use this as a template
                        # idx now contains fixed/extendable for the sub-network
                        idx = con.lhs.indexes[coord].intersection(added_flow.indexes[coord])
                        sel = {coord: idx}
                        lhs = con.lhs.sel(sel) + added_flow.sel(sel)
                        name = constraint + f"-security-for-{outage_component}-{outage_branch}-in-{sub_network}"
                        m.add_constraints(
                            lhs, con.sign.sel(sel), con.rhs.sel(sel), name=name
                        )