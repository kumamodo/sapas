import threading
from sapas.instruments.transport.base import BaseTransport
from sapas.modules import log


class VisaTransport(BaseTransport):
    """
    VISA transport (USB-TMC / GPIB / TCPIP-INSTR) using PyVISA.
    Lazy-loads pyvisa so environments without pyvisa can still run other transports.
    """

    def __init__(self, resource: str, timeout: float = 3.0, **visa_kwargs):
        self.resource_name = str(resource)
        self.timeout = float(timeout)
        self.visa_kwargs = visa_kwargs
        self._rm = None
        self._inst = None
        self._lock = threading.Lock()

    def _ensure_pyvisa(self):
        try:
            import pyvisa
            return pyvisa
        except ImportError:
            raise ImportError(
                "PyVISA is required for VISA / USB-TMC instrument control. "
                "Please install it using: pip install pyvisa pyvisa-py"
            )

    def connect(self) -> None:
        with self._lock:
            if self._inst is not None:
                return

            pyvisa = self._ensure_pyvisa()
            log.info(f"Opening VISA resource: {self.resource_name}", tag="INSTRUMENT")
            try:
                if self._rm is None:
                    self._rm = pyvisa.ResourceManager()
                self._inst = self._rm.open_resource(self.resource_name, **self.visa_kwargs)
                self._inst.timeout = int(self.timeout * 1000)  # PyVISA timeout is in ms
                log.info(f"Connected to VISA resource: {self.resource_name}", tag="INSTRUMENT")
            except Exception as e:
                log.error(f"Failed to open VISA resource {self.resource_name}: {e}", tag="INSTRUMENT")
                self._inst = None
                raise

    def close(self) -> None:
        with self._lock:
            if self._inst is not None:
                try:
                    self._inst.close()
                except Exception:
                    pass
                self._inst = None
                log.info(f"Closed VISA resource {self.resource_name}", tag="INSTRUMENT")

    def __del__(self) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._inst is not None

    def write(self, command: str) -> None:
        if not self.is_connected:
            self.connect()

        with self._lock:
            if self._inst is None:
                raise RuntimeError(f"VISA resource {self.resource_name} is not open.")
            log.info(f"TX -> {command.strip()}", tag="INSTRUMENT")
            self._inst.write(command)

    def read(self) -> str:
        if not self.is_connected:
            self.connect()

        with self._lock:
            if self._inst is None:
                raise RuntimeError(f"VISA resource {self.resource_name} is not open.")
            response = self._inst.read().strip()
            log.info(f"RX <- {response}", tag="INSTRUMENT")
            return response

    def query(self, command: str) -> str:
        if not self.is_connected:
            self.connect()

        with self._lock:
            if self._inst is None:
                raise RuntimeError(f"VISA resource {self.resource_name} is not open.")
            log.info(f"QUERY -> {command.strip()}", tag="INSTRUMENT")
            response = self._inst.query(command).strip()
            log.info(f"RX <- {response}", tag="INSTRUMENT")
            return response
