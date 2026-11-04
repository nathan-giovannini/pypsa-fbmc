import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from fbmc.core.model.constraints.main import remove_original_constraints_by_bus
from fbmc.core.model.main import remove_original_constraints_loop


class _FakeSubNetwork:
    def __init__(self, zones):
        self._zones = pd.Index(zones)

    def buses(self):
        return pd.DataFrame({"zone_name": self._zones})

    def buses_i(self):
        return pd.Index(range(len(self._zones)))


class TestConstraintRemoval(unittest.TestCase):
    def test_remove_original_constraints_loop_uses_full_removal_when_all_subnets_large(self):
        zonal_net = SimpleNamespace()
        base_case = SimpleNamespace(
            sub_networks=pd.DataFrame(
                {"obj": [_FakeSubNetwork(["A", "B", "C"]), _FakeSubNetwork(["D", "E", "F"])]}
            )
        )

        with patch("fbmc.core.model.main.remove_original_constraints") as remove_all, patch(
            "fbmc.core.model.main.remove_original_constraints_by_bus"
        ) as remove_by_bus:
            remove_original_constraints_loop(zonal_net, base_case)

        remove_all.assert_called_once_with(zonal_net)
        remove_by_bus.assert_not_called()

    def test_remove_original_constraints_by_bus_raises_before_mutating_meshed_models(self):
        model = SimpleNamespace(
            constraints={
                "Bus-nodal_balance": MagicMock(),
                "Bus-meshed-nodal_balance": MagicMock(),
            },
            remove_constraints=MagicMock(),
            add_constraints=MagicMock(),
        )
        zonal_net = SimpleNamespace(model=model)

        with self.assertRaises(NotImplementedError):
            remove_original_constraints_by_bus(zonal_net, pd.Index(["A"]))

        model.remove_constraints.assert_not_called()
        model.add_constraints.assert_not_called()


if __name__ == "__main__":
    unittest.main()
