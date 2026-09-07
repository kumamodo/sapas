from typing import Any
from sapas.instruments.power_supply.base import BasePowerSupply
from sapas.instruments.power_supply.scpi import ScpiPowerSupply
from sapas.instruments.power_supply.vendors import VENDOR_REGISTRY
from sapas.instruments.transport.base import BaseTransport


def create_power_supply(
    driver: str,
    transport: BaseTransport,
    max_voltage: float | None = None,
    max_current: float | None = None,
    **kwargs: Any
) -> BasePowerSupply:
    """
    Factory function to instantiate a PowerSupply instance based on the driver/vendor name.
    If the driver name is not recognized in VENDOR_REGISTRY, it falls back to standard ScpiPowerSupply.
    """
    driver_key = (driver or "scpi").lower().strip()
    cls = VENDOR_REGISTRY.get(driver_key)
    if cls is None:
        return ScpiPowerSupply(
            transport,
            max_voltage=max_voltage,
            max_current=max_current,
            name=driver,
            **kwargs
        )
    return cls(transport, max_voltage=max_voltage, max_current=max_current, **kwargs)
