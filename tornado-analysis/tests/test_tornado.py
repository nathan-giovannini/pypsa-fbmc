import pandas as pd
import pypsa
import pytest

from tornado_analysis.baseline import prepare_baseline
from tornado_analysis.config import expand_cases, validate_config
from tornado_analysis.model import run_model
from tornado_analysis.perturb import apply_perturbation, select_assets
from tornado_analysis.steps import step_aggregate, step_run_case

BUS_COUNTRY = {"DE1": "DE", "FR1": "FR"}


def make_network():
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.add("Bus", ["DE1", "FR1"])
    n.add("Carrier", ["gas", "wind"])
    n.add("Line", "l", bus0="DE1", bus1="FR1", x=0.1, s_nom=50)
    n.add("Load", "ld_de", bus="DE1", p_set=[100, 120, 80, 100])
    n.add("Load", "ld_fr", bus="FR1", p_set=[50, 60, 40, 50])
    n.add("Generator", "gas_de", bus="DE1", carrier="gas", p_nom=300, marginal_cost=50)
    n.add("Generator", "gas_fr", bus="FR1", carrier="gas", p_nom=100, marginal_cost=60)
    n.add("Generator", "wind_de", bus="DE1", carrier="wind", p_nom=100, marginal_cost=0,
          p_max_pu=[0.5, 0.2, 0.8, 0.5])
    return n


def case(**kw):
    base = {"parameter": "p", "direction": "up", "target": {"component": "generators", "attribute": "marginal_cost", "kind": "static"},
            "selector": {"carrier": ["gas"]}, "mode": "relative", "magnitude": 0.1}
    base.update(kw)
    return base


def test_static_relative():
    n = make_network()
    out = apply_perturbation(n, case(), BUS_COUNTRY)
    assert out.generators.loc["gas_de", "marginal_cost"] == pytest.approx(55)
    assert out.generators.loc["wind_de", "marginal_cost"] == 0
    assert n.generators.loc["gas_de", "marginal_cost"] == 50  # original untouched


def test_static_absolute_down_distributed_proportionally():
    n = make_network()
    c = case(direction="down", mode="absolute", magnitude=40,
             target={"component": "generators", "attribute": "p_nom", "kind": "static"})
    out = apply_perturbation(n, c, BUS_COUNTRY)
    assert out.generators.loc["gas_de", "p_nom"] == pytest.approx(300 - 30)
    assert out.generators.loc["gas_fr", "p_nom"] == pytest.approx(100 - 10)


def test_timeseries_relative_and_absolute():
    n = make_network()
    ts = {"component": "generators", "attribute": "p_max_pu", "kind": "timeseries"}
    out = apply_perturbation(n, case(target=ts, selector={"carrier": ["wind"]}, magnitude=0.5), BUS_COUNTRY)
    assert out.generators_t.p_max_pu["wind_de"].tolist() == pytest.approx([0.75, 0.3, 1.2, 0.75])
    out = apply_perturbation(n, case(target=ts, selector={"carrier": ["wind"]}, mode="absolute",
                                     direction="down", magnitude=0.1), BUS_COUNTRY)
    assert out.generators_t.p_max_pu["wind_de"].tolist() == pytest.approx([0.4, 0.1, 0.7, 0.4])


def test_timeseries_kind_mismatch_raises():
    n = make_network()
    with pytest.raises(ValueError):
        apply_perturbation(n, case(target={"component": "generators", "attribute": "marginal_cost", "kind": "timeseries"}), BUS_COUNTRY)
    with pytest.raises(ValueError):
        apply_perturbation(n, case(target={"component": "generators", "attribute": "nope", "kind": "static"}), BUS_COUNTRY)


def test_selector_combination_and_empty():
    n = make_network()
    assert list(select_assets(n.generators, {"carrier": ["gas"], "countries": ["FR"]}, BUS_COUNTRY)) == ["gas_fr"]
    assert list(select_assets(n.generators, {"query": "p_nom > 200"})) == ["gas_de"]
    assert list(select_assets(n.generators, {"names": ["wind_de"]})) == ["wind_de"]
    assert list(select_assets(n.lines, {"countries": ["FR"]}, BUS_COUNTRY)) == ["l"]
    with pytest.raises(ValueError):
        apply_perturbation(n, case(selector={"carrier": ["nuclear"]}), BUS_COUNTRY)


def base_cfg(perturbations):
    return {"study": "t", "network": "x.nc", "perturbations": perturbations}


def test_expand_cases_independent_directions_and_countries():
    p = {"name": "Gas", "target": {"component": "generators", "attribute": "p_nom", "kind": "static"},
         "selector": {"countries": ["DE", "FR"]}, "per_country": True, "mode": "absolute", "up": 10}
    cases = expand_cases(validate_config(base_cfg([p])))
    assert set(cases) == {"Gas_-_DE__up", "Gas_-_FR__up"}  # no 'down' case
    assert cases["Gas_-_FR__up"]["selector"]["countries"] == ["FR"]
    p2 = {**p, "per_country": False, "down": 5}
    assert set(expand_cases(validate_config(base_cfg([p2])))) == {"Gas__up", "Gas__down"}


def test_config_validation():
    t = {"component": "loads", "attribute": "p_set", "kind": "timeseries"}
    for bad in ({"name": "a", "target": t, "mode": "relative"},
                {"name": "a", "target": t, "mode": "percent", "up": 1},
                {"name": "a", "target": {**t, "kind": "x"}, "mode": "relative", "up": 1},
                {"name": "a", "target": t, "mode": "relative", "up": 1, "selector": {"foo": 1}}):
        with pytest.raises(ValueError):
            validate_config(base_cfg([bad]))


def test_baseline_fix_capacities_and_load_shedding():
    n = make_network()
    n.generators.loc["gas_de", "p_nom_extendable"] = True
    n.generators.loc["gas_de", "p_nom_opt"] = 123.0
    n = prepare_baseline(n, {"fix_optimal_capacities": True,
                             "load_shedding": {"enabled": True, "cost": 1000, "buses": {"countries": ["DE"]}}},
                         prefix_length=2)
    assert n.generators.loc["gas_de", "p_nom"] == 123.0
    assert not n.generators.loc["gas_de", "p_nom_extendable"]
    shed = n.generators[n.generators.index.str.endswith(" load shedding")]
    assert list(shed.bus) == ["DE1"]
    assert shed.marginal_cost.iloc[0] == 1000


def test_run_model_and_steps(tmp_path):
    n = prepare_baseline(make_network(), {"fix_optimal_capacities": False,
                                          "load_shedding": {"enabled": True, "cost": 1000}}, prefix_length=2)
    solver = {"name": "highs"}
    res = run_model(n, solver, 2, 3000)
    assert res["load_shedding_MWh"] == pytest.approx(0)
    assert set(res["welfare_by_country"]) == {"DE", "FR"}

    base = tmp_path / "base.nc"
    n.export_to_netcdf(str(base))
    spec = case(parameter="Gas cost", target={"component": "generators", "attribute": "marginal_cost", "kind": "static"})
    step_run_case(str(base), None, solver, 2, 3000, str(tmp_path / "cases" / "baseline"))
    step_run_case(str(base), spec, solver, 2, 3000, str(tmp_path / "cases" / "c__up"))
    step_aggregate(str(tmp_path), ["c__up"], str(tmp_path / "t.csv"), str(tmp_path / "w.csv"))
    t = pd.read_csv(tmp_path / "t.csv")
    assert list(t.direction) == ["baseline", "up"]
    assert t.loc[0, "welfare_shift"] == 0
    assert t.loc[1, "welfare_shift"] > 0
    assert (tmp_path / "cases" / "c__up" / "network.nc").exists()
    assert t.loc[1, "total_system_cost"] > t.loc[0, "total_system_cost"]
    w = pd.read_csv(tmp_path / "w.csv")
    assert {"baseline", "up"} == set(w.direction)


def test_welfare_shift_is_sum_of_absolute_changes():
    from tornado_analysis.welfare import welfare_shift
    base = pd.Series({"DE": 100.0, "FR": 50.0})
    pert = pd.Series({"DE": 90.0, "FR": 65.0, "BE": -5.0})
    assert welfare_shift(base, pert) == pytest.approx(10 + 15 + 5)


def test_infeasible_case_is_recorded_with_diagnostics(tmp_path):
    import json
    n = make_network()  # no load shedding: demand cannot be met after a deep cut
    base = tmp_path / "base.nc"
    n.export_to_netcdf(str(base))
    spec = case(parameter="Gas cut", direction="down", mode="relative", magnitude=1.0,
                target={"component": "generators", "attribute": "p_nom", "kind": "static"},
                selector={})
    out = tmp_path / "cases" / "cut__down"
    step_run_case(str(base), spec, {"name": "highs"}, 2, 3000, str(out))
    m = json.loads((out / "metrics.json").read_text())
    assert m["status"].startswith("failed")
    assert m["diagnostics"]["snapshots_with_generation_below_demand"] == 4
    assert "hint" in m["diagnostics"]
    assert (out / "network.nc").exists()
    step_run_case(str(base), None, {"name": "highs"}, 2, 3000, str(tmp_path / "cases" / "baseline"))
    step_aggregate(str(tmp_path), ["cut__down"], str(tmp_path / "t.csv"), str(tmp_path / "w.csv"))
    t = pd.read_csv(tmp_path / "t.csv")
    assert t.loc[1, "status"].startswith("failed") and pd.isna(t.loc[1, "welfare_shift"])
    assert "diagnostics" in t.columns


def test_baseline_failure_raises(tmp_path):
    from tornado_analysis.model import OptimizationError
    n = make_network()
    n.generators["p_nom"] = 0.0
    base = tmp_path / "base.nc"
    n.export_to_netcdf(str(base))
    with pytest.raises(OptimizationError):
        step_run_case(str(base), None, {"name": "highs"}, 2, 3000, str(tmp_path / "cases" / "baseline"))
