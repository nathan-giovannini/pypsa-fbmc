import logging
import pypsa
import pandas as pd
import xarray as xr

from ...settings import FBMCConfig
from ...types import InputParameters
from .base_case import prepare_base_case
from .gsk import calculate_gsk, gsk_dict_to_xarray
from .cnec import cnec_router

def calc_input_parameters(
    nodal_net: pypsa.Network,
    gsk: dict | xr.DataArray | None,
    config: FBMCConfig,
    cnecs_input=None,
) -> InputParameters:
    """
    Call all functions that calculate input parameters for the FBMC workflow.

    Args:
        nodal_net (pypsa.Network): _description_
        gsk (dict | xr.DataArray | None): _description_
        config (FBMCConfig): _description_
        cnecs_input: Custom CNECs input passed through to cnec_router when
            config.cnec_setting == CNECStrategy.CUSTOM. Defaults to None.

    Returns:
        InputParameters: _description_
    """
    base_case = prepare_base_case(
        nodal_net,
        strategy=config.base_case_strategy,
        base_case_kwargs=config.solver_kwargs
        )

    if gsk is None:
        gsk = calculate_gsk(base_case, config.gsk_strategy, config.gsk_kwargs)
    elif isinstance(gsk, dict):
        gsk = gsk_dict_to_xarray(gsk)

    cnecs = cnec_router(
        net=nodal_net,
        cnec_setting=config.cnec_setting,
        add_security_constraints=config.add_security_constraints,
        cnecs_input=cnecs_input
    )

    return InputParameters(gsk=gsk, cnecs=cnecs, base_case=base_case)