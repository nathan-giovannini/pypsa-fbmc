import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import xarray as xr

from fbmc.enums import GSKStrategy
from fbmc.settings import FBMCConfig
from fbmc.core.parameters.main import calculate_fbmc_parameters_subnet
from fbmc.core.parameters.security_constrained import apply_bodf


class TestApplyBodfColumnwiseEquivalence(unittest.TestCase):

	def test_columnwise_and_vectorized_paths_match(self):
		# da has dims=(branch, snapshot); values are arbitrary but deterministic.
		da = xr.DataArray(
			data=[
				[10.0, -2.5, 0.0],
				[-4.0, 8.0, 5.5],
				[7.5, 1.0, -3.0],
				[3.0, -6.0, 9.0],
			],
			coords={
				"branch": pd.Index(["L1", "L2", "L3", "L4"], name="branch"),
				"snapshot": ["t0", "t1", "t2"],
				"branch_component": ("branch", ["Line", "Line", "Line", "Line"]),	
			},
			dims=["branch", "snapshot"],
		)

		cnec_index = pd.MultiIndex.from_tuples(
			[
				("L1", "L2"),
				("L3", "L1"),
				("L4", "L3"),
				("L2", "L4"),
				("L1", "L3"),
			],
			names=["branch", "outage"],
		)

		bodf = xr.DataArray(
			data=[0.2, -0.15, 0.05, -0.3, 0.1],
			coords={
				"cnec": cnec_index,
				# "branch": ("cnec", cnec_index.get_level_values("branch").values),
				# "outage": ("cnec", cnec_index.get_level_values("outage").values),
				"branch_component": ("cnec", ["Line", "Line", "Line", "Line", "Line"]),
				"outage_component": ("cnec", ["Line", "Line", "Line", "Line", "Line"]),
				},
			dims=["cnec"],
			name="BODF",
		)

		# Force vectorized path.
		out_vectorized = apply_bodf(da, bodf, matrix_size_limit=None)

		# Force columnwise path.
		out_columnwise = apply_bodf(da, bodf, matrix_size_limit=0)

		xr.testing.assert_identical(out_columnwise, out_vectorized)


class TestSecurityConstrainedParameterAlignment(unittest.TestCase):

	def test_reduced_cnec_outputs_stay_aligned(self):
		reduced_cnecs = xr.Dataset(
			coords={
				"cnec": pd.Index(["c1", "c2"], name="cnec"),
			}
		).coords
		z_ptdf = xr.DataArray(
			[[1.0, -1.0], [0.5, -0.5]],
			coords={"cnec": reduced_cnecs["cnec"], "Zone": ["A", "B"]},
			dims=["cnec", "Zone"],
		)
		upper_ram = xr.DataArray(
			[100.0, 80.0],
			coords={"cnec": reduced_cnecs["cnec"]},
			dims=["cnec"],
		)
		lower_ram = xr.DataArray(
			[-100.0, -80.0],
			coords={"cnec": reduced_cnecs["cnec"]},
			dims=["cnec"],
		)
		fake_subnet = SimpleNamespace(
			buses_i=lambda: pd.Index(["A1", "B1", "B2"]),
			buses=lambda: pd.DataFrame({"zone_name": ["A", "B", "B"]}),
		)
		input_parameters_subnet = SimpleNamespace(
			base_case=fake_subnet,
			gsk=xr.DataArray(
				[[1.0, 0.0, 0.0], [0.0, 0.5, 0.5]],
				coords={"Zone": ["A", "B"], "Bus": ["A1", "B1", "B2"]},
				dims=["Zone", "Bus"],
			),
			cnecs=xr.Dataset(
				coords={"cnec": pd.Index(["c1", "c2", "c3"], name="cnec")}
			).coords,
		)
		config = FBMCConfig(add_security_constraints=True, gsk_strategy=GSKStrategy.P_NOM)

		with patch("fbmc.core.parameters.main.get_subnetwork_bodf", return_value="bodf"), \
			patch("fbmc.core.parameters.main.calc_subnet_ptdf_security_constrained") as calc_ptdf, \
			patch("fbmc.core.parameters.main.get_base_flows_subnet_security_constrained") as calc_base_flows, \
			patch("fbmc.core.parameters.main.calc_base_net_positions_subnet", return_value="base-np"), \
			patch("fbmc.core.parameters.main.calculate_zonal_ptdf", return_value=z_ptdf), \
			patch("fbmc.core.parameters.main.calculate_ram", return_value=(upper_ram, lower_ram)):
			calc_ptdf.return_value = xr.DataArray(
				[[1.0], [2.0]],
				coords={"cnec": reduced_cnecs["cnec"], "Bus": ["A1"]},
				dims=["cnec", "Bus"],
			)
			calc_base_flows.return_value = xr.DataArray(
				[[10.0], [20.0]],
				coords={"cnec": reduced_cnecs["cnec"], "snapshot": ["t0"]},
				dims=["cnec", "snapshot"],
			)

			result = calculate_fbmc_parameters_subnet(input_parameters_subnet, config)

		self.assertListEqual(list(result.cnecs["cnec"].values), ["c1", "c2"])
		self.assertListEqual(list(result.z_ptdf.coords["cnec"].values), ["c1", "c2"])
		self.assertListEqual(list(result.upper_ram.coords["cnec"].values), ["c1", "c2"])
		self.assertListEqual(list(result.lower_ram.coords["cnec"].values), ["c1", "c2"])


if __name__ == "__main__":
		unittest.main()
