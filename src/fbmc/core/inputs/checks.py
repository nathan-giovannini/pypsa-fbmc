import logging
from collections.abc import Sequence

import pypsa

from fbmc.enums import CNECStrategy

logger = logging.getLogger(__name__)

def check_reactance(nodal_net):
    if ((nodal_net.lines.x <= 0) & (nodal_net.lines.type == "")).any():
        raise ValueError("Lines with non-positive reactance found.")
    if ((nodal_net.transformers.x <= 0) & (nodal_net.transformers.type == "")).any():
        raise ValueError("Transformers with non-positive reactance found.")

def check_no_lines_or_transformers_in_zonal_net(zonal_net: pypsa.Network):
    """Checks that there are no lines or transformers in the zonal network, as these should be represented either as links or nothing
    (since fbmc constraints will be added)

    """

    if (zonal_net.lines.index).any():
        raise ValueError("Lines found in zonal network.")
    if (zonal_net.transformers.index).any():
        raise ValueError("Transformers found in zonal network.")
    if (zonal_net.links.index).any():
        logger.warning(
            "%s links found in the zonal network. Make sure they represent HVDC connections, not NTCs. Link indices: %s",
            len(zonal_net.links.index),
            zonal_net.links.index,
        )


def check_custom_cnecs(cnecs_input, add_security_constraints):
    if cnecs_input is None:
        raise ValueError(
            "cnec_setting is CUSTOM but no cnecs were provided. "
            "Pass a cnecs argument to run_fbmc()."
        )
    if isinstance(cnecs_input, str) or not isinstance(cnecs_input, Sequence):
        raise ValueError(
            "cnecs must be a Sequence of Sequences (e.g. a list of tuples). "
            "See fbmc.core.inputs.cnec.cnec_subnet_router() for the expected format."
        )
    if not all(isinstance(item, Sequence) and not isinstance(item, str) for item in cnecs_input):
        raise ValueError(
            "Each element of cnecs must itself be a Sequence (e.g. a tuple). "
            "See fbmc.core.inputs.cnec.cnec_subnet_router() for the expected format."
        )
    if add_security_constraints:
        if not all(isinstance(cnec[0], tuple | list) for cnec in cnecs_input):
            raise ValueError(
                "When add_security_constraints is True, each element of cnecs must be a Sequence of Sequences"
                "e.g. (('Line', 'line_1'), ('Transformer', 'trafo_1')) can be one of the elements in cnecs_input. "
            )
        if not all(isinstance(cnec[0][0], str) and isinstance(cnec[0][1], str) for cnec in cnecs_input):
            raise ValueError(
                "When add_security_constraints is True, each element of cnecs must be a Sequence of Sequences"
                "e.g. (('Line', 'line_1'), ('Transformer', 'trafo_1')) can be one of the elements in cnecs_input. "
            )
    else:
        if not all(isinstance(cnec[0], str) and isinstance(cnec[1], str) for cnec in cnecs_input):
            raise ValueError(
                "When add_security_constraints is False, each element of cnecs must be a Sequence of two strings"
                "e.g. ('Line', 'line_1') can be one of the elements in cnecs_input. "
            )



def do_input_checks(nodal_net, zonal_net, gsk_dict, config, cnecs_input=None):
    check_reactance(nodal_net)
    check_no_lines_or_transformers_in_zonal_net(zonal_net)
    if config.cnec_setting == CNECStrategy.CUSTOM:
        check_custom_cnecs(cnecs_input, config.add_security_constraints)
    else:
        if cnecs_input is not None:
            raise ValueError(
                "cnec_setting is not CUSTOM but cnecs were provided. "
                "Set cnec_setting to CUSTOM or remove the cnecs argument."
            )
