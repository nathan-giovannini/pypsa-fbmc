import unittest

import numpy as np
import pypsa

from fbmc.core.parameters.ptdf import _get_subnetwork_ptdf


class TestGetNetworkPtdf(unittest.TestCase):
    def setUp(self):
        self.basecase_network = pypsa.Network()
        self.basecase_network.set_snapshots(range(2))
        self.basecase_network.add("Bus", "bus1", v_nom=220)
        self.basecase_network.add("Bus", "bus2", v_nom=220)
        self.basecase_network.add("Bus", "bus3", v_nom=220)
        self.basecase_network.add(
            "Line",
            "line1",
            bus0="bus1",
            bus1="bus2",
            x=0.2,
            r=0.01,
            b=0.001,
            s_nom=300,
        )
        self.basecase_network.add(
            "Line",
            "line2",
            bus0="bus1",
            bus1="bus3",
            x=0.2,
            r=0.01,
            b=0.001,
            s_nom=300,
        )
        self.basecase_network.add(
            "Line",
            "line3",
            bus0="bus2",
            bus1="bus3",
            x=0.2,
            r=0.01,
            b=0.001,
            s_nom=200,
        )

    def test_get_network_ptdf(self):
        self.basecase_network.determine_network_topology()
        sub_network = self.basecase_network.sub_networks.obj.iloc[0]
        ptdf = _get_subnetwork_ptdf(sub_network).to_pandas()
        self.assertEqual(ptdf.columns.tolist(), ["bus1", "bus2", "bus3"])
        self.assertEqual(ptdf.index.tolist(), ["line1", "line2", "line3"])
        self.assertFalse((ptdf == 0).all().all(), "PTDF matrix should not be all zeros")

        ref_bus = "bus1"
        for line_name in ptdf.index:
            line = self.basecase_network.lines.loc[line_name]
            if line.bus0 == ref_bus or line.bus1 == ref_bus:
                self.assertTrue(
                    np.isclose(ptdf.loc[line_name].sum(), -1.0),
                    f"Sum of PTDF row for {line_name} connected to reference bus should be close to -1",
                )
            else:
                self.assertTrue(
                    np.isclose(ptdf.loc[line_name].sum(), 0.0),
                    f"Sum of PTDF row for {line_name} not connected to reference bus should be close to 0",
                )


if __name__ == "__main__":
    unittest.main()
