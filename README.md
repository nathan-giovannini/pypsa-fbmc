# pypsa-fbmc

`pypsa-fbmc` adds Flow-Based Market Coupling (FBMC) workflows to
[`PyPSA`](https://pypsa.readthedocs.io).

It is built around an object-oriented API on `pypsa.Network`:

- `nodal_net.fbmc.to_zonal(...)`
- `zonal_net.fbmc.run(...)`
- `zonal_net.fbmc.create_model(...)`
- `zonal_net.fbmc.solve()`
- `zonal_net.fbmc.results()`

Redispatch is available as an **optional** workflow on top of FBMC. It is not part of the
default clearing path.

## First-time user guide

### 1. Install the package

Requires Python 3.11+.

```bash
git clone https://github.com/WouterKoksNL/pypsa-fbmc
cd pypsa-fbmc
pip install .
```

### 2. Install a solver

The default configuration uses **Gurobi**. You can also use another solver supported by
`linopy`, for example HiGHS, by changing `config.solver_kwargs["solver_name"]`.

### 3. Prepare a nodal PyPSA network

At minimum, your nodal network should contain:

- buses
- generators and/or other supply components
- loads
- AC branches with valid reactances
- a `zone_name` column on `nodal_net.buses`

### 4. Convert the nodal network to a zonal one

```python
zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])
```

### 5. Run FBMC

For most users, the recommended path is the one-step workflow:

```python
import fbmc

config = fbmc.FBMCConfig.from_base_yaml()
result = zonal_net.fbmc.run(nodal_net, config)
```

### 6. Inspect the result

```python
print(result.net_positions)
print(result.dispatch_results.generators_p)
print(result.fbmc_parameters)
```

## Minimal example

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

nodal_net.buses.loc[:, "zone_name"] = ["A", "B", "B"]
zonal_net = nodal_net.fbmc.to_zonal(nodal_net.buses["zone_name"])

config = fbmc.FBMCConfig.from_base_yaml()
result = zonal_net.fbmc.run(nodal_net, config)
```

## Step-by-step workflow

If you want to inspect the intermediate stages:

```python
zonal_net.fbmc.create_model(nodal_net, config)
zonal_net.fbmc.solve()
result = zonal_net.fbmc.results()
```

Use this path for debugging, learning, or advanced inspection of the model state.

## Optional redispatch

Redispatch lives outside the core FBMC run path:

```python
rd_net, rd_cost = fbmc.redispatch.run(
    nodal_net,
    result.dispatch_results,
)
```

Only use redispatch if you explicitly want a second workflow after market clearing.

## Documentation

Full documentation is in `docs/` and published at
[pypsa-fbmc.readthedocs.io](https://pypsa-fbmc.readthedocs.io/en/latest/).
