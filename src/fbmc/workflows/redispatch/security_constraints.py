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
                outages = branches_i.difference(bridges)
            else:
                outages = branches_i.intersection(branch_outages)

            if outages.empty:
                continue
            sub_network.calculate_BODF()
            BODF = pd.DataFrame(sub_network.BODF, index=branches_i, columns=branches_i)[
                outages
            ]

            for c_outage, c_affected in product(
                outages.unique(0), branches_i.unique(0)
            ):
                c_outage_ = c_outage + "-outage"
                c_outages = outages.get_loc_level(c_outage)[1]
                flow_outage = m.variables[c_outage + "-s"].loc[:, c_outages]
                flow_outage = flow_outage.rename({c_outage: c_outage_})

                bodf = BODF.loc[c_affected, c_outage]
                bodf = xr.DataArray(bodf, dims=[c_affected, c_outage_])
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
                    name = constraint + f"-security-for-{c_outage_}-in-{sub_network}"
                    m.add_constraints(
                        lhs, con.sign.sel(sel), con.rhs.sel(sel), name=name
                    )