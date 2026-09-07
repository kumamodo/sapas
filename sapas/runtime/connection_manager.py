from sapas.drivers.ssh import SSHDriver
from sapas.drivers.adb import ADBDriver
from sapas.drivers.serial import SerialDriver
from sapas.modules.log import warn

class ConnectionManager:
    def __init__(self, config):
        self._config = config
        self._connections = {}

    def get(self, name, new=False):
        if name == "adb_device":
            warn("[DEPRECATION] Link target 'adb_device' is deprecated and will be removed in future versions. Please migrate to 'adb_usb' or 'adb_network'.", tag='LINK')
            if name not in self._config and "adb_usb" in self._config:
                name = "adb_usb"

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
            ssh_params = {key: value for key, value in cfg.items() if key in ("host", "user", "password", "stop_chars", "source_ip")}
            return SSHDriver(**ssh_params)       
        elif type_ == "udp":
            from sapas.drivers.udp.driver import UDPDriver
            udp_params = {
                "host": cfg.get("host"),
                "server_port": cfg.get("server_port"),
                "client_port": cfg.get("client_port", 5088),
                "timeout": cfg.get("timeout", 0.1),
                "drain_timeout": cfg.get("drain_timeout", 0.05)
            }
            return UDPDriver(**udp_params)
        elif type_ == "adb":
            adb_params = {key: value for key, value in cfg.items() if key in ("usb_serial", "network_host")}
            return ADBDriver(**adb_params)
        elif type_ == "uart":
            serial_params = {key: value for key, value in cfg.items() if key in ("port", "baudrate", "timeout", "stop_chars")}
            return SerialDriver(**serial_params)
        elif type_ in ("power_supply", "psu"):
            return self._create_power_supply(cfg)
        else:
            raise ValueError(f"Unsupported connection type: {type_}")

    def _create_power_supply(self, cfg):
        # Determine transport configuration
        trans_cfg = cfg.get("transport")
        if not isinstance(trans_cfg, dict):
            trans_cfg = cfg

        trans_type = str(trans_cfg.get("type") or trans_cfg.get("transport_type") or "tcp").lower()

        if trans_type in ("tcp", "socket", "lan"):
            from sapas.instruments.transport.socket import SocketTransport
            host = trans_cfg.get("host") or trans_cfg.get("ip")
            if not host:
                raise ValueError("TCP power supply requires 'host' or 'ip' configuration.")
            port = trans_cfg.get("port")
            if not port:
                raise ValueError("TCP power supply requires 'port' configuration (e.g. 2268 for GW-Instek, 7001 for XULIAN).")
            timeout = trans_cfg.get("timeout", 3.0)
            transport = SocketTransport(host=host, port=int(port), timeout=float(timeout))

        elif trans_type in ("uart", "serial", "com"):
            from sapas.instruments.transport.serial import SerialTransport
            port = trans_cfg.get("port") or trans_cfg.get("com_port")
            if not port:
                raise ValueError("Serial power supply requires 'port' configuration (e.g. 'COM4' or '/dev/ttyUSB0').")
            baudrate = trans_cfg.get("baudrate", 9600)
            timeout = trans_cfg.get("timeout", 1.0)
            transport = SerialTransport(port=str(port), baudrate=int(baudrate), timeout=float(timeout))

        elif trans_type in ("visa", "usbtmc", "tmc"):
            from sapas.instruments.transport.visa import VisaTransport
            resource = trans_cfg.get("resource") or trans_cfg.get("address") or trans_cfg.get("resource_name")
            if not resource:
                raise ValueError("VISA power supply requires 'resource' configuration (e.g. 'USB0::0x2EC7::...::INSTR').")
            timeout = trans_cfg.get("timeout", 3.0)
            transport = VisaTransport(resource=str(resource), timeout=float(timeout))

        else:
            raise ValueError(f"Unsupported transport type for power supply: {trans_type}")

        # Protection limits
        prot = cfg.get("protection", {})
        if not isinstance(prot, dict):
            prot = {}
        max_voltage = prot.get("max_voltage", cfg.get("max_voltage"))
        max_current = prot.get("max_current", cfg.get("max_current"))

        # Driver profile
        driver = cfg.get("driver", "scpi")
        from sapas.instruments.power_supply import create_power_supply
        return create_power_supply(
            driver=driver,
            transport=transport,
            max_voltage=max_voltage,
            max_current=max_current
        )

    def close_all(self):
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()