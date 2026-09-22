

import pandas as pd
import numpy as np
import logging
import pypsa
import xarray as xr

from fbmc.enums import CNECStrategy

from ..parameters.bridge_branches import find_bridges_sub_network

logger = logging.getLogger(__name__)


def cnecs_from_combinatorial_cne_and_outages(cnes: xr.Coordinates, outages: xr.Coordinates) -> xr.Coordinates:
    """Create a MultiIndex of (cne, outage) pairs for all combinations of cnes and outages, excluding pairs where cne == outage."""
    mask = cnes['branch'] != outages['outage']  # broadcasts to (branch, outage)
    cnecs_stacked = mask.where(mask).stack(cnec=('branch', 'outage')).dropna('cnec').coords

    return cnecs_stacked


def cnec_router(
        net: pypsa.Network,
        cnec_setting: CNECStrategy,
        add_security_constraints: bool,
        **kwargs
        ) -> dict[str, xr.Coordinates]:
    """Router function to determine CNECs based on the configuration. This function can be extended in the future to include more complex logic for determining CNECs.
    """
    cnecs_dict = {}
    subnet_fn = cnec_subnet_router if add_security_constraints else cne_subnet_router
    for subnet in net.sub_networks.obj:
        cnecs = subnet_fn(subnet, cnec_setting, **kwargs)
        cnecs_dict[subnet.name] = cnecs
    return cnecs_dict


def cne_subnet_router(
        sub_network: pypsa.SubNetwork,
        cnec_setting: CNECStrategy,
        cnecs_input: list = None
        ) -> xr.Coordinates:
    """_summary_

    Args:
        sub_network (pypsa.SubNetwork): _description_
        cnec_setting (CNECStrategy): _description_
        cnecs_input: 
            cnecs_input should be structured like 
        
                Sequence of tuples like (cne_type, branch_name) where cne_type is either 'Line' or 'Transformer'.
                Example: [('Line', 'line_1'), ('Transformer', 'trafo_1')]

        Defaults to None.

    Raises:
        ValueError: _description_


    Returns:
        xr.Coordinates: _description_
    """
    if cnec_setting == CNECStrategy.ALL:
        return define_all_cnes(sub_network)
    elif cnec_setting == CNECStrategy.CUSTOM:
        return define_cnes_from_input(sub_network, cnecs_input)
    else:
        raise ValueError(f'cnec_setting {cnec_setting.value} not recognized. Choices are "all", "manual".')



def cnec_subnet_router(
        sub_network: pypsa.SubNetwork,
        cnec_setting: CNECStrategy,
        cnecs_input: list = None
        ) -> xr.Coordinates:
    """_summary_

    Args:
        sub_network (pypsa.SubNetwork): _description_
        cnec_setting (CNECStrategy): _description_
        add_security_constraints (bool): _description_
        cnec_input: 
            cnec_input can be structured like 
        
                Sequence of tuples like (cne_type, branch_name) where cne_type is either 'line' or 'transformer'.
                which defines the CNEs, which are then transformed into a MultiIndex of (cne, outage) pairs for all combinations of cnes and outages, excluding pairs where cne == outage. 
                In this case, all line/trafo outages are considered, not just the CNEs. 
                Example: [('line', 'line_1'), ('transformer', 'trafo_1')]

        Defaults to None.

    Raises:
        ValueError: _description_
        NotImplementedError: _description_
        ValueError: _description_

    Returns:
        xr.Coordinates: _description_
    """
    bridge_branches = find_bridges_sub_network(sub_network)

    logging.info(f"Identified {len(bridge_branches)} bridge branches that will be excluded from CNECs: {bridge_branches}.")
    if cnec_setting == CNECStrategy.ALL:
        if cnecs_input is not None:
            raise ValueError("cnecs_input should be None when cnec_setting is 'ALL'.")
        return define_all_cnecs(sub_network, bridge_branches)
    elif cnec_setting == CNECStrategy.CUSTOM:
        return define_cnecs_from_input(sub_network, cnecs_input, bridge_branches)
    else:
        raise ValueError(f'cnec_setting {cnec_setting.value} not recognized. Choices are "all", "manual".')


def define_all_cnes(sub_network: pypsa.SubNetwork) -> xr.Coordinates:
    cnes = sub_network.branches().index.droplevel(0)
    cnes = xr.DataArray(
        data=cnes.values,
        coords={'branch': cnes.values},
        dims=['branch']
    ).assign_coords(branch_component=('branch', sub_network.branches().index.get_level_values(0).values))
    return cnes


def define_all_cnecs(sub_network: pypsa.SubNetwork, bridge_branches: pd.MultiIndex) -> xr.Coordinates:
    cnes = define_all_cnes(sub_network)
    mask = ~xr.DataArray(
        np.isin(cnes.coords['branch'].values, bridge_branches.coords['branch'].values),
        dims='branch'
    )
    outages = cnes.sel(branch=mask).copy().rename({'branch': 'outage', 'branch_component': 'outage_component'})
    cnecs = cnecs_from_combinatorial_cne_and_outages(cnes, outages)
    return cnecs

def define_cnes_from_input(
        sub_network: pypsa.SubNetwork,
        cnes_input: list,
) -> xr.Coordinates:
    
    all_branches = sub_network.branches()
    # Format 1: (cne_type, branch_name) — CNEs only; all outages considered
    cne_tuples = [
        (cne_type.capitalize(), branch_name)
        for cne_type, branch_name in cnes_input
        if (cne_type.capitalize(), branch_name) in all_branches.index
    ]
    if not cne_tuples:
        raise ValueError(
            f"No custom CNEs match branches in sub-network '{sub_network.name}'. "
            "Check that branch names and component types ('line'/'transformer') are correct."
        )
    cne_names = [t[1] for t in cne_tuples]
    cne_components = [t[0] for t in cne_tuples]
    cnes = xr.DataArray(
        data=cne_names,
        coords={'branch': cne_names},
        dims=['branch']
    ).assign_coords(branch_component=('branch', cne_components))
    return cnes


def define_cnecs_from_input(
        sub_network: pypsa.SubNetwork,
        cnecs_input: list,
        bridge_branches: pd.MultiIndex,
) -> xr.Coordinates:
    all_branches = sub_network.branches()
    
    correct_format = isinstance(cnecs_input[0][0], (tuple, list))
    if not correct_format:
        raise ValueError(
            "Invalid format for cnecs_input. Since security constraints are enabled,\n"
            "CNECs expected format is\n"
            "[((cne_type, cne_name), (outage_type, outage_name)), ...]\n"
            f"got {type(cnecs_input[0])}."
        )

    cnec_tuples = [
        ((cne[0].capitalize(), cne[1]), (out[0].capitalize(), out[1]))
        for cne, out in cnecs_input
        if (cne[0].capitalize(), cne[1]) in all_branches.index
        and (out[0].capitalize(), out[1]) in all_branches.index
    ]
    if not cnec_tuples:
        raise ValueError(
            f"No custom CNECs match branches in sub-network '{sub_network.name}'. "
            "Check that branch names and component types ('line'/'transformer') are correct."
        )
    cne_names = [t[0][1] for t in cnec_tuples]
    cne_components = [t[0][0] for t in cnec_tuples]
    outage_names = [t[1][1] for t in cnec_tuples]
    outage_components = [t[1][0] for t in cnec_tuples]

    bridge_outages = [name for name in outage_names if name in bridge_branches.coords['branch'].values]
    if bridge_outages:
        raise ValueError(
            f"Custom CNECs contain bridge branches as outages: {bridge_outages}. "
            "Bridge branches cannot be outages as they would disconnect the network."
        )

    cnec_mi = pd.MultiIndex.from_arrays(
        [cne_names, outage_names], names=['branch', 'outage']
    )
    cnecs = xr.Dataset(
        coords={
            'cnec': cnec_mi,
            'branch_component': ('cnec', cne_components),
            'outage_component': ('cnec', outage_components),
        }
    ).coords
    return cnecs

def filter_on_cne(ptdf_parameter: pd.DataFrame, cne_lines: list) -> pd.DataFrame:
    """
    Filters the PTDF parameter DataFrame to include only the specified critical network elements (CNEs).
    Args:
        ptdf_parameter (pd.DataFrame): A DataFrame with a multi-index, where the second level of the index 
                                        represents the critical network elements.
        cne_lines (list): A list of critical network elements to filter on.
    Returns:
        pd.DataFrame: A DataFrame filtered to include only the specified critical network elements, 
                        with the original multi-index restored and index names removed.
    Example:
        >>> import pandas as pd
        >>> data = {
        ...     'level_0': ['A', 'A', 'B', 'B'],
        ...     'level_1': ['CNE1', 'CNE2', 'CNE1', 'CNE3'],
        ...     'value': [10, 20, 30, 40]
        ... }
        >>> df = pd.DataFrame(data).set_index(['level_0', 'level_1'])
        >>> cne_lines = ['CNE1', 'CNE3']
        >>> filter_on_cne(df, cne_lines)
                value
        A CNE1     10
        B CNE1     30
        B CNE3     40
    """
    
    # Get the critical network elements (level_1) equal to the cne_lines
    cne_filtered_parameter = ptdf_parameter[ptdf_parameter.index.isin(cne_lines)]

    return cne_filtered_parameter
