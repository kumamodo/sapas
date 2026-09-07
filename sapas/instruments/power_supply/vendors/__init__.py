from typing import Type
from sapas.instruments.power_supply.base import BasePowerSupply
from sapas.instruments.power_supply.vendors.gw_instek import GWInstekPowerSupply
from sapas.instruments.power_supply.vendors.itech import ItechPowerSupply
from sapas.instruments.power_supply.vendors.xulian import XulianPowerSupply

VENDOR_REGISTRY: dict[str, Type[BasePowerSupply]] = {
    "gw_instek": GWInstekPowerSupply,
    "gw-instek": GWInstekPowerSupply,
    "gw": GWInstekPowerSupply,
    "itech": ItechPowerSupply,
    "it": ItechPowerSupply,
    "xulian": XulianPowerSupply,
    "x_ulian": XulianPowerSupply,
}

__all__ = [
    "GWInstekPowerSupply",
    "ItechPowerSupply",
    "XulianPowerSupply",
    "VENDOR_REGISTRY",
]
