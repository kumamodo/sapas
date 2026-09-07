from sapas.instruments.power_supply.scpi import ScpiPowerSupply
from sapas.instruments.transport.base import BaseTransport


class GWInstekPowerSupply(ScpiPowerSupply):
    """
    Driver profile for GW Instek Power Supplies (e.g. PSU-30-108, GPP series).
    Supports both Serial and LAN connections.
    """

    def __init__(
        self,
        transport: BaseTransport,
        max_voltage: float | None = None,
        max_current: float | None = None,
        **kwargs
    ):
        super().__init__(
            transport,
            max_voltage=max_voltage,
            max_current=max_current,
            name="GW-Instek-PSU",
            use_numeric_output=kwargs.get("use_numeric_output", True),
            settle_delay=kwargs.get("settle_delay", 0.1)
        )

    def connect(self) -> None:
        super().connect()
        try:
            self.clear()
        except Exception:
            pass
