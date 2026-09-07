import re
import time
from sapas.instruments.power_supply.base import BasePowerSupply
from sapas.instruments.transport.base import BaseTransport
from sapas.modules import log


class ScpiPowerSupply(BasePowerSupply):
    """
    Standard SCPI-99 compliant Power Supply implementation.
    Compatible with the majority of programmable bench power supplies
    (GW-Instek, ITECH, Keysight, Rigol, Siglent, etc.).
    """

    def __init__(
        self,
        transport: BaseTransport,
        max_voltage: float | None = None,
        max_current: float | None = None,
        name: str = "ScpiPowerSupply",
        use_numeric_output: bool = False,
        settle_delay: float = 0.2
    ):
        super().__init__(transport, max_voltage=max_voltage, max_current=max_current, name=name)
        self.use_numeric_output = use_numeric_output
        self.settle_delay = settle_delay

    def identify(self) -> str:
        """Query instrument identification string via *IDN?"""
        return self.transport.query("*IDN?")

    def clear(self) -> None:
        """Clear instrument status via *CLS"""
        self.transport.write("*CLS")

    def reset(self) -> None:
        """Reset instrument to default state via *RST"""
        self.transport.write("*RST")
        time.sleep(self.settle_delay)

    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        self._validate_voltage(voltage)
        log.info(f"[{self.name}] Setting Voltage: {voltage} V", tag="PSU")
        self.transport.write(f"VOLT {voltage}")
        if self.settle_delay > 0:
            time.sleep(self.settle_delay)

    def set_current(self, current: float, channel: int = 1) -> None:
        self._validate_current(current)
        log.info(f"[{self.name}] Setting Current Limit: {current} A", tag="PSU")
        self.transport.write(f"CURR {current}")
        if self.settle_delay > 0:
            time.sleep(self.settle_delay)

    def output_on(self, voltage: float | None = None, current: float | None = None, channel: int = 1) -> None:
        if voltage is not None:
            self.set_voltage(voltage, channel=channel)
        if current is not None:
            self.set_current(current, channel=channel)

        log.info(f"[{self.name}] Turning Output ON", tag="PSU")
        cmd = "OUTP 1" if self.use_numeric_output else "OUTP ON"
        self.transport.write(cmd)
        if self.settle_delay > 0:
            time.sleep(self.settle_delay)

    def output_off(self, channel: int = 1) -> None:
        log.info(f"[{self.name}] Turning Output OFF", tag="PSU")
        cmd = "OUTP 0" if self.use_numeric_output else "OUTP OFF"
        self.transport.write(cmd)
        if self.settle_delay > 0:
            time.sleep(self.settle_delay)

    def _parse_float_response(self, raw_str: str) -> float:
        """
        Cleans and extracts floating point values from raw instrument responses.
        Handles variations like '12.05V', ' 12.05 ', 'V 12.05\\r\\n', etc.
        """
        cleaned = raw_str.strip()
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cleaned)
        if not match:
            raise ValueError(f"[{self.name}] Unable to parse float number from response: '{raw_str}'")
        return float(match.group(0))

    def measure_voltage(self, channel: int = 1) -> float:
        raw = self.transport.query("MEAS:VOLT?")
        val = self._parse_float_response(raw)
        log.info(f"[{self.name}] Measured Voltage: {val} V", tag="PSU")
        return val

    def measure_current(self, channel: int = 1) -> float:
        raw = self.transport.query("MEAS:CURR?")
        val = self._parse_float_response(raw)
        log.info(f"[{self.name}] Measured Current: {val} A", tag="PSU")
        return val
