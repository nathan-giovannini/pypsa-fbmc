import pandas as pd
import pypsa


def extract_model_results(net: pypsa.Network):
        gen_p = pd.DataFrame(
            net.model.solution['Generator-p'].values,
            index=net.snapshots, 
            columns=net.generators.index
        )
        net.generators_t.p = gen_p

        net.loads_t.p = net.loads_t.p_set

        if not net.storage_units.empty:
            storage_p = pd.DataFrame(
            net.model.solution['StorageUnit-p_dispatch'].values - net.model.solution['StorageUnit-p_store'].values,
            index=net.snapshots, 
            columns=net.storage_units.index
            )
            net.storage_units_t.p = storage_p
            storage_soc = pd.DataFrame(
                net.model.solution['StorageUnit-state_of_charge'].values,
                index=net.snapshots, 
                columns=net.storage_units.index
            )
            net.storage_units_t.state_of_charge = storage_soc
        if not net.links.empty:
            links_p = pd.DataFrame(
                net.model.solution['Link-p'].values,
                index=net.snapshots, 
                columns=net.links.index
            )

            net.links_t.p0 = links_p
            net.links_t.p1 = -links_p
        return 
