from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pypsa
import xarray as xr


def _shape_summary(obj: pd.DataFrame | xr.DataArray | dict[Any, pd.DataFrame] | None) -> str:
    if obj is None:
        return "None"
    if isinstance(obj, pd.DataFrame):
        return f"DataFrame{obj.shape}"
    if isinstance(obj, xr.DataArray):
        return f"DataArray{obj.shape}"
    if isinstance(obj, dict):
        n_snapshots = len(obj)
        if n_snapshots == 0:
            return "dict(0 snapshots)"
        first_df = next(iter(obj.values()))
        return f"dict({n_snapshots} snapshots, frame_shape={first_df.shape})"
    return type(obj).__name__


def _network_summary(net: pypsa.Network) -> str:
    name = net.name or "Unnamed Network"
    component_attrs = [
        ("buses", "Bus"),
        ("generators", "Generator"),
        ("loads", "Load"),
        ("lines", "Line"),
        ("links", "Link"),
        ("storage_units", "StorageUnit"),
        ("stores", "Store"),
        ("transformers", "Transformer"),
        ("sub_networks", "SubNetwork"),
    ]
    parts: list[str] = []
    for attr_name, label in component_attrs:
        if hasattr(net, attr_name):
            count = len(getattr(net, attr_name))
            if count > 0:
                parts.append(f"{label}:{count}")

    snapshots = len(net.snapshots) if hasattr(net, "snapshots") else "?"
    components = ", ".join(parts) if parts else "none"
    return f"{name} | snapshots={snapshots} | components=[{components}]"


@dataclass 
class InputParametersSubnet:
    gsk: xr.DataArray
    cnecs: xr.Coordinates
    base_case: pypsa.SubNetwork

@dataclass
class InputParameters:
    gsk: xr.DataArray
    cnecs: dict[str, xr.Coordinates]
    base_case: pypsa.Network

    def for_subnet(self, subnet_name: str) -> InputParametersSubnet:
        if subnet_name not in self.cnecs:
            raise ValueError(f"Subnet {subnet_name} not found in cnecs.")
        gsk_subnet = self.gsk.sel(
            Bus=self.base_case.sub_networks.obj[subnet_name].buses_i(),
            Zone=self.base_case.sub_networks.obj[subnet_name].buses().zone_name.unique()
        )
        return InputParametersSubnet(
            gsk=gsk_subnet,
            cnecs=self.cnecs[subnet_name],
            base_case=self.base_case.sub_networks.obj[subnet_name]
        )


@dataclass
class FBMCModelState:
    config: Any
    input_parameters: InputParameters
    fbmc_parameters: dict[str, "SubnetFBMCParameters"]
    solved: bool = False
    result: "FBMCResult | None" = None

    @property
    def base_case(self) -> pypsa.Network:
        return self.input_parameters.base_case

@dataclass
class SubnetFBMCParameters:
    z_ptdf: xr.DataArray 
    upper_ram: xr.DataArray
    lower_ram: xr.DataArray
    cnecs: xr.Coordinates
    zones: pd.Index

    def __repr__(self) -> str:
        return (
            "SubnetFBMCParameters("
            f"z_ptdf={_shape_summary(self.z_ptdf)}, "
            f"upper_ram={_shape_summary(self.upper_ram)}, "
            f"lower_ram={_shape_summary(self.lower_ram)}, "
            f"cnecs={len(self.cnecs)}, "
            f"zones={len(self.zones)}, "
            ")"
        )

    __str__ = __repr__


class DispatchResult:    
    def __init__(self, net: pypsa.Network):
        self.generators_p: pd.DataFrame = net.generators_t.p
        self.storage_units_p: pd.DataFrame = net.storage_units_t.p

        self.links_p0: pd.DataFrame = net.links_t.p0
        self.storage_levels: pd.DataFrame | None = None
        self.water_values: xr.DataArray | None = None
        if not net.storage_units.empty:
            self.storage_levels = net.storage_units_t.state_of_charge
            if "StorageUnit-energy_balance" in net.model.dual: # needs seperate check as dual is not returned in case the problem is a MILP
                self.water_values: xr.DataArray = net.model.dual["StorageUnit-energy_balance"]

    def __repr__(self) -> str:
        return (
            "DispatchResult object with attrs: "
            f"\n  generators_p: {self.generators_p.shape} snapshots x generators, "
            f"\n  storage_units_p: {self.storage_units_p.shape} snapshots x storage units, "
            f"\n  links_p0: {self.links_p0.shape} snapshots x links, "
            f"\n  storage_levels: {self.storage_levels.shape if self.storage_levels is not None else None} snapshots x storage levels, "
            f"\n  water_values: {self.water_values.shape if self.water_values is not None else None} snapshots x water values"
        )

    __str__ = __repr__



@dataclass
class FBMCResult:
    zonal_net: pypsa.Network
    net_positions: pd.DataFrame
    dispatch_results: DispatchResult
    fbmc_parameters: dict[str, "SubnetFBMCParameters"]
    base_case: pypsa.Network

    def __str__(self) -> str:
        subnet_keys = list(self.fbmc_parameters.keys())
        key_preview = ", ".join(map(str, subnet_keys[:5]))
        if len(subnet_keys) > 5:
            key_preview += ", ..."

        return (
            "FBMCResult\n"
            f"  zonal_net: {_network_summary(self.zonal_net)}\n"
            f"  base_case: {_network_summary(self.base_case)}\n"
            f"  net_positions: DataFrame{self.net_positions.shape}\n"
            f"  dispatch_results: {self.dispatch_results}\n"
            f"  fbmc_parameters: {len(self.fbmc_parameters)} subnet(s) [{key_preview}]"
        )

    __repr__ = __str__
