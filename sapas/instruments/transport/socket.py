import socket
import threading
import time
from sapas.instruments.transport.base import BaseTransport
from sapas.modules import log


class SocketTransport(BaseTransport):
    """
    Direct TCP socket transport for instruments over LAN / Ethernet.
    Suitable for instruments listening on raw TCP ports (e.g. GW-Instek on 2268, XULIAN on 7001).
    """

    def __init__(self, host: str, port: int, timeout: float = 3.0, terminator: str = "\n"):
        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)
        self.terminator = terminator
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        with self._lock:
            if self._sock is not None:
                return
            log.info(f"Connecting to TCP instrument at {self.host}:{self.port} (timeout={self.timeout}s)", tag="INSTRUMENT")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                self._sock = sock
                log.info(f"Connected to {self.host}:{self.port}", tag="INSTRUMENT")
            except Exception as e:
                log.error(f"Failed to connect to {self.host}:{self.port}: {e}", tag="INSTRUMENT")
                self._sock = None
                raise

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
                log.info(f"Closed TCP connection to {self.host}:{self.port}", tag="INSTRUMENT")

    def __del__(self) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def write(self, command: str) -> None:
        if not self.is_connected:
            self.connect()

        if not command.endswith(self.terminator):
            command_to_send = command + self.terminator
        else:
            command_to_send = command

        with self._lock:
            if self._sock is None:
                raise RuntimeError(f"Socket connection to {self.host}:{self.port} is not open.")
            log.info(f"TX -> {command.strip()}", tag="INSTRUMENT")
            self._sock.sendall(command_to_send.encode("utf-8"))

    def read(self) -> str:
        if not self.is_connected:
            self.connect()

        with self._lock:
            if self._sock is None:
                raise RuntimeError(f"Socket connection to {self.host}:{self.port} is not open.")
            
            buffer = bytearray()
            start_time = time.time()
            term_bytes = self.terminator.encode("utf-8")

            while True:
                try:
                    chunk = self._sock.recv(1024)
                    if not chunk:
                        raise ConnectionResetError(f"Connection closed by instrument at {self.host}:{self.port}")
                    buffer.extend(chunk)
                    if term_bytes in buffer:
                        break
                except socket.timeout:
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"Timed out after {self.timeout}s waiting for response from {self.host}:{self.port}")

            response = buffer.decode("utf-8", errors="replace").strip()
            log.info(f"RX <- {response}", tag="INSTRUMENT")
            return response
