from sapas.instruments.power_supply.scpi import ScpiPowerSupply
from sapas.instruments.transport.base import BaseTransport


class XulianPowerSupply(ScpiPowerSupply):
    """
    Driver profile for XULIAN Power Supplies.
    Supports LAN Socket on Port 7001 (SCPI) or Serial.
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
            name="XULIAN-PSU",
            use_numeric_output=kwargs.get("use_numeric_output", False),
            settle_delay=kwargs.get("settle_delay", 0.1)
        )

    def connect(self) -> None:
        super().connect()
        try:
            self.clear()
        except Exception:
            pass
