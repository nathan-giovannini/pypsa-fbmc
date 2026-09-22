import pandas as pd
import pypsa
from pathlib import Path


def apply_unit_commitment_data(
    net: pypsa.Network,
    unit_commitment_path: str,
) -> None:
    """Apply per-carrier unit-commitment parameters to nodal generators if enabled."""

    unit_commitment_path = Path(unit_commitment_path)
    if not unit_commitment_path.exists():
        raise FileNotFoundError(f"Unit commitment file not found: {unit_commitment_path}")
    uc_df = pd.read_csv(unit_commitment_path, index_col="attribute")

    carrier_set = set(net.generators.carrier.astype(str))
    available_carriers = [carrier for carrier in uc_df.columns if carrier in carrier_set]
    if not available_carriers:
        raise ValueError("No matching carriers found between unit commitment data and nodal net generators. Check the unit commitment file and the nodal net generator carriers.")

    for carrier in available_carriers:
        generator_mask = net.generators.carrier.astype(str) == carrier
        # UC attributes only have an effect when committable is enabled.
        net.generators.loc[generator_mask, "committable"] = True

        for attribute, value in uc_df[carrier].items():
            net.generators.loc[generator_mask, attribute] = value
