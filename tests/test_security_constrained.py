import unittest

import pandas as pd
import xarray as xr

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


if __name__ == "__main__":
		unittest.main()
