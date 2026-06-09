from sapas.drivers.ssh import SSHDriver
from sapas.drivers.adb import ADBDriver

class ConnectionManager:
    def __init__(self, config):
        self._config = config
        self._connections = {}

    def get(self, name, new=False):
        if name not in self._config:
            raise ValueError(f"Unknown connection: {name}")

        cfg = self._config[name]
        # new = True → always create a new instance.
        if new:
            return self._create(cfg)

        # reuse: if it doesn’t exist in the cache, create one.
        if name not in self._connections:
            conn = self._create(cfg)
            self._connections[name] = conn
        else:
            conn = self._connections[name]

        # Only connect when there is no existing connection.
        if not getattr(conn, "_connected", False):
            conn.connect()

        return conn

    def _create(self, cfg):
        type_ = cfg["type"]

        if type_ == "ssh":
            ssh_params = {key: value for key, value in cfg.items() if key in ("host", "user", "password", "stop_chars")}
            return SSHDriver(**ssh_params)       
        elif type_ == "udp":
            from sapas.drivers.udp.driver import UDPDriver
            udp_params = {
                "host": cfg.get("host"),
                "server_port": cfg.get("server_port"),
                "client_port": cfg.get("client_port", 5088),
                "timeout": cfg.get("timeout", 0.1)
            }
            return UDPDriver(**udp_params)
        elif type_ == "adb":
            adb_params = {key: value for key, value in cfg.items() if key in ("usb_serial", "network_host")}
            return ADBDriver(**adb_params)
        elif type_ == "com":
            return SerialDriver(**cfg)
        else:
            raise ValueError(f"Unsupported connection type: {type_}")

    def close_all(self):
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()