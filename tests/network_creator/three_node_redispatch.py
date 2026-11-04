import pypsa
import pandas as pd

from fbmc.network.network_conversion import nodal_to_zonal

def create_three_node_redispatch_case():
        nodal_net = pypsa.Network()
        nodal_net.set_snapshots(['1', '2'])
        nodal_net.add('Bus', ['A1', 'B1', 'B2'])
        nodal_net.buses.loc[:, 'zone_name'] = ['A', 'B', 'B']
        nodal_net.add('Line', 'B1-A1', bus0='B1', bus1='A1', x=1, s_nom=9)
        nodal_net.add('Line', 'B1-B2', bus0='B1', bus1='B2', x=1, s_nom=9)
        nodal_net.add('Line', 'A1-B2', bus0='A1', bus1='B2', x=1, s_nom=9)

        nodal_net.add('Generator', 'gen_A1', bus='A1', p_nom=100, marginal_cost=400, carrier="Oil")
        nodal_net.add('Generator', 'gen_B1', bus='B1', p_nom=100, marginal_cost=100, carrier="Wind")
        nodal_net.add('Generator', 'gen_B2', bus='B2', p_nom=100, marginal_cost=120, carrier="CCGT")
        nodal_net.add('Load', 'load_A1', bus='A1', p_set=[18, 18])

        zonal_net = nodal_to_zonal(nodal_net.copy(), nodal_net.buses.zone_name)
        zonal_net.remove('Link', zonal_net.links.index)
        # nodal_net.optimize(solver_name='gurobi')

        gsk = pd.DataFrame(0., index=zonal_net.buses.index, columns=nodal_net.buses.index)
        gsk.index.name = "Zone"
        gsk.loc['A', 'A1'] = 1.0
        gsk.loc['B', 'B1'] = 0.5
        gsk.loc['B', 'B2'] = 0.5
        gsk_dict = {snapshot: gsk.copy() for snapshot in zonal_net.snapshots}
        output = {
            'zonal_net': zonal_net,
            'nodal_net': nodal_net,
            'gsk_dict': gsk_dict
        }
        return output