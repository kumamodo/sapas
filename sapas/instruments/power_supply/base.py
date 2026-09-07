from abc import abstractmethod
from sapas.instruments.base import BaseInstrument
from sapas.instruments.transport.base import BaseTransport
from sapas.modules import log


class BasePowerSupply(BaseInstrument):
    """
    Abstract base class for all DC Power Supplies.
    Enforces hardware safety protection limits and unified operational APIs.
    """

    def __init__(
        self,
        transport: BaseTransport,
        max_voltage: float | None = None,
        max_current: float | None = None,
        name: str = "PowerSupply"
    ):
        self.transport = transport
        self.max_voltage = float(max_voltage) if max_voltage is not None else None
        self.max_current = float(max_current) if max_current is not None else None
        self.name = name

    def connect(self) -> None:
        self.transport.connect()

    def close(self) -> None:
        self.transport.close()

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected

    @property
    def _connected(self) -> bool:
        return self.is_connected

    def _validate_voltage(self, voltage: float) -> None:
        if voltage < 0:
            raise ValueError(f"[{self.name}] Voltage cannot be negative: {voltage}V")
        if self.max_voltage is not None and voltage > self.max_voltage:
            raise ValueError(
                f"[{self.name}] Safety Violation! Requested voltage {voltage}V exceeds configured max_voltage limit of {self.max_voltage}V"
            )

    def _validate_current(self, current: float) -> None:
        if current < 0:
            raise ValueError(f"[{self.name}] Current limit cannot be negative: {current}A")
        if self.max_current is not None and current > self.max_current:
            raise ValueError(
                f"[{self.name}] Safety Violation! Requested current {current}A exceeds configured max_current limit of {self.max_current}A"
            )

    @abstractmethod
    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """Set output voltage in Volts."""
        pass

    @abstractmethod
    def set_current(self, current: float, channel: int = 1) -> None:
        """Set current limit in Amperes."""
        pass

    def set_vol_curr(self, voltage: float | None = None, current: float | None = None, channel: int = 1) -> None:
        """Set both voltage and current limit."""
        if voltage is not None:
            self.set_voltage(voltage, channel=channel)
        if current is not None:
            self.set_current(current, channel=channel)

    @abstractmethod
    def output_on(self, voltage: float | None = None, current: float | None = None, channel: int = 1) -> None:
        """
        Enable power output. Optionally specify voltage and/or current to configure before enabling.
        """
        pass

    @abstractmethod
    def output_off(self, channel: int = 1) -> None:
        """Disable power output."""
        pass

    @abstractmethod
    def measure_voltage(self, channel: int = 1) -> float:
        """Measure real-time output voltage in Volts."""
        pass

    @abstractmethod
    def measure_current(self, channel: int = 1) -> float:
        """Measure real-time output current in Amperes."""
        pass

    # Aliases for backward compatibility with common script conventions
    def get_voltage(self, channel: int = 1) -> float:
        return self.measure_voltage(channel=channel)

    def get_current(self, channel: int = 1) -> float:
        return self.measure_current(channel=channel)
