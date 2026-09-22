import pypsa
import pandas as pd
import unittest

import fbmc
from fbmc.enums import GSKStrategy
from fbmc.network.network_conversion import nodal_to_zonal
from fbmc.post_processing.main import get_slack_zones
from fbmc.post_processing.market_prices import calculate_zonal_prices


class TestFBMCResults(unittest.TestCase):
    
    def mock_config(self):
        config = fbmc.FBMCConfig()
        config.reliability_margin_factor = 0.0
        config.gsk_strategy = GSKStrategy.ADJUSTABLE_CAP
        config.add_security_constraints = False
        return config

    def setup_network(self):
        nodal_net = pypsa.Network()
        nodal_net.set_snapshots(['1', '2'])
        nodal_net.add('Bus', ['A1', 'B1', 'B2'])
        nodal_net.buses.loc[:, 'zone_name'] = ['A', 'B', 'B']
        nodal_net.add('Line', 'A1-B1', bus0='B1', bus1='A1', x=1, s_nom=10)
        nodal_net.add('Line', 'A2-B1', bus0='B2', bus1='A1', x=1, s_nom=10)
        nodal_net.add('Line', 'A1-A2', bus0='B1', bus1='B2', x=1, s_nom=10)
        
        nodal_net.add('Generator', 'gen_A1', bus='A1', p_nom=12, marginal_cost=400, carrier="Wind")
        nodal_net.add('Generator', 'gen_B1', bus='B1', p_nom=12, marginal_cost=100, carrier="CCGT")
        nodal_net.add('Generator', 'gen_B2', bus='B2', p_nom=12, marginal_cost=200, carrier="Oil")
        nodal_net.add('Load', 'load_A1', bus='A1', p_set=[15, 15])
        return nodal_net
    

    def run_fbmc(self, nodal_net):
        nodal_net.optimize(solver_name='gurobi')
        zonal_net = nodal_to_zonal(nodal_net, nodal_net.buses.zone_name)
        config = fbmc.FBMCConfig()

        config.reliability_margin_factor = 0.0
        config.gsk_strategy = GSKStrategy.ADJUSTABLE_CAP
        zonal_net.loads_t.p_set = zonal_net.loads_t.p_set * (18/15)

        gsk = pd.DataFrame(0., index=zonal_net.buses.index, columns=nodal_net.buses.index)
        gsk.loc['A', 'A1'] = 1.0
        gsk.loc['B', 'B1'] = 0.8
        gsk.loc['B', 'B2'] = 0.2
        gsk.columns.name = "Bus"
        gsk.index.name = "Zone"
        gsk_dict = {snapshot: gsk.copy()
            for snapshot in zonal_net.snapshots}

        result = zonal_net.fbmc.run(nodal_net, config=config, gsk=gsk_dict)
        return nodal_net, zonal_net, result
    
    def test_obj_value(self):
        """Test that the objective value is as expected."""
        nodal_net = self.setup_network()
        nodal_net, zonal_net, _ = self.run_fbmc(nodal_net)
        assert abs(zonal_net.model.objective.value - 5333.3333) < 1e-3

    def test_line_direction_invariance(self):
        """Reversing the direction of lines should not change the objective value.
        An exception here can mean that minRAM is not calculated correctly or that the minRAM constraint is not enforced. """
        nodal_net = self.setup_network()
        nodal_net, zonal_net, _ = self.run_fbmc(nodal_net)
        obj1 = zonal_net.model.objective.value

        # Reverse line direction
        nodal_net.lines.loc['A1-B1', ['bus0', 'bus1']] = ['A1', 'B1']
        nodal_net.lines.loc['A2-B1', ['bus0', 'bus1']] = ['A1', 'B2']
        # nodal_net.lines.loc['A1-A2', ['bus0', 'bus1']] = ['B1', 'B2']

        nodal_net, zonal_net, _ = self.run_fbmc(nodal_net)
        obj2 = zonal_net.model.objective.value

        assert abs(obj1 - obj2) < 1e-6
    
    def test_price_calculation(self):
        """Test that the price calculation runs without errors."""
        nodal_net = self.setup_network()
        nodal_net, zonal_net, result = self.run_fbmc(nodal_net)

        z_ptdf = {
            subnet_name: params.z_ptdf
            for subnet_name, params in result.fbmc_parameters.items()
        }
        slack_zone_map = get_slack_zones(result.base_case.buses)
        prices = calculate_zonal_prices(
            zonal_net.buses.index,
            zonal_net.snapshots,
            z_ptdf,
            zonal_net.model,
            slack_zone_map,
        )
        assert prices is not None
        assert not prices.isna().any().any()
        assert abs(prices.loc['1', 'A'] - 400.) < 1e-3
        assert abs(prices.loc['1', 'B'] - 200.) < 1e-3

    def test_create_model_can_be_called_twice(self):
        nodal_net = self.setup_network()
        zonal_net = nodal_to_zonal(nodal_net, nodal_net.buses.zone_name)
        config = self.mock_config()

        zonal_net.fbmc.create_model(nodal_net, config)
        first_constraints = set(zonal_net.model.constraints)

        zonal_net.fbmc.create_model(nodal_net, config)
        second_constraints = set(zonal_net.model.constraints)

        self.assertEqual(first_constraints, second_constraints)
        self.assertIn("Zone-definition", second_constraints)
        