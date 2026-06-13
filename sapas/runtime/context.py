from datetime import datetime

from sapas.runtime.connection_manager import ConnectionManager
from sapas.drivers.ssh import SSHDriver
from sapas.drivers.adb import ADBDriver
from sapas.drivers.udp.driver import UDPDriver
from sapas.drivers.serial import SerialDriver

_DEPRECATION_WARNING_SHOWN = False


class _BaseTypedManager:
    def __init__(self, conn_mgr, driver_type):
        self._conn_mgr = conn_mgr
        self._driver_type = driver_type

    def get(self, name, **kwargs):
        conn = self._conn_mgr.get(name, **kwargs)

        if not isinstance(conn, self._driver_type):
            raise TypeError(f"{name} is not a {self._driver_type.__name__}")

        return conn

class ExecutionContext:
    # Internal components should use self.ctx directly
    # while end-users are encouraged to use the sapas.var proxy.
    def __init__(self, station_cfg: dict, project_cfg: dict, env_cfg: dict = None):
        self.station = station_cfg or {}
        self.project = project_cfg or {}
        self.env = env_cfg or {}
        
        self.config = {}
        self.external = {}
        self.runtime = {}

        # Merge all configurations; the order determines the priority.
        self._merge_config()

        # Get the link from the merged configuration.
        link_configs = self.config.get("LINK")
        if link_configs is None:
            link_configs = self.config.get("link")
            if link_configs is not None:
                deprecation_warnings = self.runtime.setdefault('_DEPRECATION_WARNINGS', [])
                deprecation_warnings.append("The lowercase 'link' configuration key in >> project.yaml << is deprecated and will be removed in future versions. Please use uppercase 'LINK' instead.")
                global _DEPRECATION_WARNING_SHOWN
                if not _DEPRECATION_WARNING_SHOWN:
                    import sys
                    import time
                    sys.stderr.write("\n[  WARN  ] [DEPRECATION] The lowercase 'link' configuration key in >> project.yaml << is deprecated and will be removed in future versions. Please use uppercase 'LINK' instead.\n")
                    sys.stderr.write("[  WARN  ] Pausing for 10 seconds to encourage migration to uppercase 'LINK' in >> project.yaml <<...\n\n")
                    sys.stderr.flush()
                    time.sleep(10)
                    _DEPRECATION_WARNING_SHOWN = True
        
        if link_configs is None:
            link_configs = {}

        self.link = ConnectionManager(link_configs)

        self.ssh = _BaseTypedManager(self.link, SSHDriver)
        self.adb = _BaseTypedManager(self.link, ADBDriver)
        self.udp = _BaseTypedManager(self.link, UDPDriver)
        self.uart = _BaseTypedManager(self.link, SerialDriver)

    def _merge_config(self):
        # Later entries override earlier ones.
        self.config = {
            **self.station, 
            **self.project, 
            **self.env
        }

    def inject_sf(self, sf_data: dict):
        self.external.update(sf_data)

    def set(self, key, value):
        if key == 'ERROR_CODE' and value == 'PASS':
            current = self.runtime.get(key)
            if current not in (None, 'PASS', 'FAIL'):
                return
        self.runtime[key] = value

    def get(self, key: str, default=None):
        """
        Retrieves a value from runtime, external, or config storage.
        Supports dot-notation for nested dictionary access (e.g., 'PROJECT.NAME').
        """
        # Look up runtime first (it is usually flattened here).
        if key in self.runtime:
            return self.runtime[key]

        # Prepare the lookup scope.
        search_scopes = [self.external, self.config]

        for scope in search_scopes:
            # If there is a direct match, return it immediately.
            if key in scope:
                return scope[key]
            
            # If it contains dots, try resolving it as a nested path.
            if "." in key:
                parts = key.split(".")
                val = scope
                for part in parts:
                    if isinstance(val, dict) and part in val:
                        val = val[part]
                    else:
                        val = None
                        break
                
                if val is not None:
                    return val

        return default
    
    def reset(self):
        """
        Resets the dynamic state of the context for a new test cycle.
        Clears per-DUT data while protecting station-level configurations.
        """
        # Protected keys that must survive the reset to maintain framework operation.
        PROTECTED_SYSTEM_KEYS = {
            'WORKSPACE_ROOT',
            'PROJECT_NAME',
            'STATION_NAME',
            'RUNNER_LOGGER',
            'IS_FAIL_STOP',
            'IS_EXCEPTION_STOP'
        }

        # Reset runtime context, preserving only the protected system variables.
        self.runtime = {
            key: value 
            for key, value in self.runtime.items() 
            if key in PROTECTED_SYSTEM_KEYS
        }

        # Wipe externally injected data (e.g. SN, shopfloor info) for the next DUT.
        self.external = {}
        
    def to_dict(self) -> dict:
        """
        Serializes the current execution context state into a dictionary.
        This includes static configurations, external injections, and runtime variables.
        """
        def _get_serializable_only(data_map: dict):
            # Keep only basic data types to avoid errors when serializing objects to YAML.
            valid_types = (str, int, float, bool, list, dict, type(None))
            return {k: v for k, v in data_map.items() if isinstance(v, valid_types)}

        return {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "project": self.get("CURRENT_PROJECT_NAME"),
                "station": self.get("CURRENT_STATION_NAME")
            },
            "configuration": _get_serializable_only(self.config),
            "external_data": _get_serializable_only(self.external),
            "runtime_context": _get_serializable_only(self.runtime)
        }