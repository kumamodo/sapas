import threading
import time
import serial
from sapas.instruments.transport.base import BaseTransport
from sapas.modules import log


class SerialTransport(BaseTransport):
    """
    Serial (RS-232 / USB Virtual COM) transport for instruments.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 1.0,
        terminator: str = "\n",
        **serial_kwargs
    ):
        self.port = str(port)
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.terminator = terminator
        self.serial_kwargs = serial_kwargs
        self._ser: serial.Serial | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            if self._ser is not None and self._ser.is_open:
                return

            log.info(f"Opening Serial port {self.port} at {self.baudrate} baud (timeout={self.timeout}s)", tag="INSTRUMENT")
            try:
                ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.timeout,
                    **self.serial_kwargs
                )
                self._ser = ser
                log.info(f"Opened Serial port {self.port}", tag="INSTRUMENT")
            except Exception as e:
                log.error(f"Failed to open Serial port {self.port}: {e}", tag="INSTRUMENT")
                self._ser = None
                raise

    def close(self) -> None:
        with self._lock:
            if self._ser is not None:
                try:
                    if self._ser.is_open:
                        self._ser.close()
                except Exception:
                    pass
                self._ser = None
                log.info(f"Closed Serial port {self.port}", tag="INSTRUMENT")

    def __del__(self) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def write(self, command: str) -> None:
        if not self.is_connected:
            self.connect()

        if not command.endswith(self.terminator):
            command_to_send = command + self.terminator
        else:
            command_to_send = command

        with self._lock:
            if self._ser is None or not self._ser.is_open:
                raise RuntimeError(f"Serial port {self.port} is not open.")
            log.info(f"TX -> {command.strip()}", tag="INSTRUMENT")
            self._ser.write(command_to_send.encode("utf-8"))
            self._ser.flush()

    def read(self) -> str:
        if not self.is_connected:
            self.connect()

        with self._lock:
            if self._ser is None or not self._ser.is_open:
                raise RuntimeError(f"Serial port {self.port} is not open.")

            raw_bytes = self._ser.readline()
            if not raw_bytes:
                raise TimeoutError(f"Timed out after {self.timeout}s waiting for serial response on {self.port}")

            response = raw_bytes.decode("utf-8", errors="replace").strip()
            log.info(f"RX <- {response}", tag="INSTRUMENT")
            return response
