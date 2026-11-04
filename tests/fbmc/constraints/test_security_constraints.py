
import unittest
import pandas as pd
import numpy as np
import pypsa
from fbmc.core.parameters.security_constrained import add_security_constraints
from fbmc.network.network_conversion import nodal_to_zonal

class TestSecurityConstraints(unittest.TestCase):

    def setUp(self):
        # Create a sample zonal network for testing
        self.zonal_net = pd.DataFrame({
            'bus': ['bus1', 'bus2', 'bus3'],
            'zone_name': ['Z1', 'Z2', 'Z3']
        })
        self.nodal_net = pypsa.examples.scigrid_de()

        quadrant1 = (self.nodal_net.buses.y > 51) & (self.nodal_net.buses.x > 9)
        quadrant2 = (self.nodal_net.buses.y > 51) & (self.nodal_net.buses.x < 9)
        quadrant3 = (self.nodal_net.buses.y < 51) & (self.nodal_net.buses.x < 9)
        quadrant4 = (self.nodal_net.buses.y < 51) & (self.nodal_net.buses.x > 9)

        # find buses in each quadrant
        buses_q1 = self.nodal_net.buses[quadrant1]
        buses_q2 = self.nodal_net.buses[quadrant2]
        buses_q3 = self.nodal_net.buses[quadrant3]
        buses_q4 = self.nodal_net.buses[quadrant4]

        self.nodal_net.buses.loc[buses_q1.index, 'zone_name'] = 'Z1'
        self.nodal_net.buses.loc[buses_q2.index, 'zone_name'] = 'Z2'
        self.nodal_net.buses.loc[buses_q3.index, 'zone_name'] = 'Z3'
        self.nodal_net.buses.loc[buses_q4.index, 'zone_name'] = 'Z4'
        # Load your network data into `net`
        self.snapshots = self.nodal_net.snapshots
        self.branch_outages = self.nodal_net.passive_branches().index

        # Call the function
        self.nodal_net.add('Generator', self.nodal_net.buses.index, bus=self.nodal_net.buses.index, p_nom=5000, marginal_cost=1000)
        self.zonal_net = nodal_to_zonal(self.nodal_net)

    def test_add_security_constraints(self):
        # Test the add_security_constraints function
        self.setUp()
        result = add_security_constraints(self.nodal_net, self.zonal_net, self.snapshots, branch_outages=self.branch_outages)
        # self.assertIsInstance(result, pd.DataFrame)