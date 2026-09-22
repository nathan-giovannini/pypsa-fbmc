# pypsa-fbmc

This package adds FBMC capabilities for the pypsa package. It further introduces several methods for GSK calculation.

## Documentation

Initial documentation can be found at [pypsa-fbmc.readthedocs.io](https://pypsa-fbmc.readthedocs.io/en/latest/).


## Example

Recommended one-step workflow:

```python
import pypsa
import fbmc

# --- build a simple three-node network ---
nodal_net = pypsa.Network()
nodal_net.set_snapshots(["1", "2"])
nodal_net.add("Bus", ["A1", "B1", "B2"])

nodal_net.add("Line", "B1-A1", bus0="B1", bus1="A1", x=1, s_nom=12)
nodal_net.add("Line", "B1-B2", bus0="B1", bus1="B2", x=1, s_nom=12)
nodal_net.add("Line", "A1-B2", bus0="A1", bus1="B2", x=1, s_nom=12)
nodal_net.add("Generator", "gen_A1", bus="A1", p_nom=100, marginal_cost=400)
nodal_net.add("Generator", "gen_B1", bus="B1", p_nom=100, marginal_cost=100)
nodal_net.add("Generator", "gen_B2", bus="B2", p_nom=100, marginal_cost=200)
nodal_net.add("Load", "load_A1", bus="A1", p_set=[15, 15])

# --- set the zone_name attribute to map buses to zones ---
nodal_net.buses.loc[:, "zone_name"] = ["A", "B", "B"]
# --- derive the zonal network (one bus per zone) ---
zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])

# --- recommended one-step run ---
config = fbmc.FBMCConfig.from_base_yaml()
result = zonal_net.fbmc.run(nodal_net, config)
```

Step-by-step workflow for debugging or teaching:

```python
zonal_net.fbmc.create_model(nodal_net, config)
zonal_net.fbmc.solve()
result = zonal_net.fbmc.results()
```

Optional redispatch lives outside the core FBMC workflow and can be run separately from
`fbmc.workflows.redispatch`.

