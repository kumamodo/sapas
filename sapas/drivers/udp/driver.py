import socket
import select
from sapas.modules.log import log

class UDPDriver:
    def __init__(self, host, server_port, client_port=5088, timeout=0.1):
        self.host = host
        self.server_port = int(server_port)
        self.client_port = int(client_port)
        self.timeout = timeout
        self.sock = None
        self._connected = False

    def connect(self):
        if self.sock is None:
            log('UDP', f"Initializing UDP link -> {self.host}:{self.server_port} (Bind Local: {self.client_port})")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.settimeout(self.timeout)
            try:
                self.sock.bind(('', self.client_port))
                self._connected = True
            except Exception as e:
                log('UDP', f"Failed to bind UDP port {self.client_port}: {e}")
                self._connected = False
                raise

    def exec(self, command, timeout=None, **kwargs):
        if not self._connected:
            self.connect()

        current_timeout = timeout or self.timeout
        
        # Automatically handle both string and bytes inputs.
        data = command.encode('utf-8') if isinstance(command, str) else command
        cmd_text = command if isinstance(command, str) else command.decode('utf-8', 'ignore')
        
        log('UDP', f"EXEC -> {cmd_text}")
        
        try:
            # Flush the receive buffer to remove stale data from previous test runs.
            while True:
                ready = select.select([self.sock], [], [], 0.0)[0]
                if not ready:
                    break
                self.sock.recvfrom(4096)

            # Send command.
            self.sock.sendto(data, (self.host, self.server_port))
            
            response = ""
            # For the first packet, wait up to current_timeout
            ready = select.select([self.sock], [], [], current_timeout)[0]
            
            if ready:
                chunk, addr = self.sock.recvfrom(4096)
                response += chunk.decode('utf-8', 'ignore')
                
                # Subsequent packets: use a very short timeout (0.01s)
                # to quickly drain any remaining buffered data.
                while True:
                    more_ready = select.select([self.sock], [], [], 0.01)[0]
                    if not more_ready:
                        # No more data available; exit immediately to avoid wasting production time.
                        break
                    chunk, addr = self.sock.recvfrom(4096)
                    response += chunk.decode('utf-8', 'ignore')
                    
            return response
        except Exception as e:
            log('UDP', f"UDP communication error: {e}")
            return ""

    def is_alive(self):
        return self.sock is not None and self._connected

    def close(self):
        if self.sock:
            log('UDP', f"Closing UDP socket on port {self.client_port}")
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self._connected = False

    def __repr__(self):
        return f"<UDPDriver {self.host}:{self.port} (local:{self.client_port})>"