import subprocess
import logging
from sapas.modules.log import info, warn, error, log

class ADBDriver:
    """
    Automatic dual-mode ADB Driver.
    Prioritizes USB connection, falls back to Network (TCP/IP) connection.
    """
    def __init__(self, usb_serial=None, network_host=None, **kwargs):
        self.usb_serial = usb_serial
        self.network_host = network_host
        self.current_serial = None
        self._connected = False

    def _run_adb(self, args, timeout=None):
        """Helper to run adb commands with consistent error handling."""
        cmd = ['adb'] + args
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            err_msg = "The 'adb' executable was not found. Please ensure Android Platform Tools are installed and 'adb' is in your system PATH."
            error(err_msg, tag='ADB')
            raise RuntimeError(err_msg)
        except Exception as e:
            raise e

    def _get_available_devices(self):
        """Returns a list of connected device serials."""
        result = self._run_adb(['devices'])
        devices = []
        for line in result.stdout.splitlines():
            if '\tdevice' in line:
                serial = line.split('\t')[0]
                devices.append(serial)
        return devices

    def connect(self):
        """
        Connects strictly based on configuration without silent fallback:
        - If network_host is specified: connects strictly via Network ADB (TCP/IP).
        - Otherwise (usb_serial specified or default): connects strictly via Physical USB.
        """
        if self.is_alive():
            return

        # Mode A: Strict Network (LAN/TCP-IP) ADB
        if self.network_host:
            info(f"Attempting Strict Network ADB connection to [{self.network_host}]", tag='ADB')
            try:
                connect_result = self._run_adb(['connect', self.network_host])
                if "connected to" in connect_result.stdout.lower() or self._check_device(self.network_host):
                    self.current_serial = self.network_host
                    self._connected = True
                    info(f"Connected to ADB device via Network [{self.network_host}]", tag='ADB')
                    return
            except Exception as e:
                error(f"Network ADB connection attempt failed: {e}", tag='ADB')

            self._connected = False
            self.current_serial = None
            err_msg = f"Failed to connect to Network ADB device [{self.network_host}]"
            error(err_msg, tag='ADB')
            raise ConnectionError(err_msg)

        # Mode B: Strict Physical USB ADB
        target_usb = self.usb_serial
        if not target_usb:
            available = self._get_available_devices()
            usb_devices = [d for d in available if ':' not in d]
            if usb_devices:
                target_usb = usb_devices[0]
                if len(usb_devices) > 1:
                    warn(f"Multiple USB devices found {usb_devices}. Auto-selecting the first one: {target_usb}", tag='ADB')
            else:
                info("No physical USB ADB devices found via auto-discovery.", tag='ADB')

        if target_usb and self._check_device(target_usb):
            self.current_serial = target_usb
            self._connected = True
            info(f"Connected to ADB device via Physical USB [{target_usb}]", tag='ADB')
            return

        self._connected = False
        self.current_serial = None
        err_msg = f"Failed to connect to physical USB ADB device (Serial: {self.usb_serial or 'AUTO'}). Ensure physical USB cable is connected."
        error(err_msg, tag='ADB')
        raise ConnectionError(err_msg)

    def _check_device(self, serial):
        """Checks if a specific ADB device is available and responding."""
        try:
            result = self._run_adb(['-s', serial, 'get-state'], timeout=2)
            return result.returncode == 0 and "device" in result.stdout.strip()
        except (subprocess.SubprocessError, RuntimeError):
            return False

    def exec(self, command, timeout=30, **kwargs):
        """Executes a shell command on the ADB device."""
        self.ensure_connected()

        info(f'[CMD]: {command}', tag='ADB')
        
        try:
            result = self._run_adb(['-s', self.current_serial, 'shell', command], timeout=timeout)
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            error(f"ADB command timeout ({timeout}s): {command}", tag='ADB')
            return "TIMEOUT ERROR"
        except Exception as e:
            error(f"ADB execution error: {e}", tag='ADB')
            return str(e)

    def is_alive(self):
        """Checks if the current connection is still active."""
        if not self._connected or not self.current_serial:
            return False
        return self._check_device(self.current_serial)

    def ensure_connected(self):
        """Ensures the connection is active, reconnecting if necessary."""
        if not self.is_alive():
            self.connect()

    def reconnect(self):
        """Forces a reconnection."""
        self.close()
        self.connect()

    def close(self):
        """Closes the connection."""
        if self.current_serial == self.network_host:
            info(f"Disconnecting ADB network device [{self.network_host}]", tag='ADB')
            try:
                self._run_adb(['disconnect', self.network_host])
            except Exception:
                pass
        
        self._connected = False
        self.current_serial = None

    def __repr__(self):
        return f"<ADBDriver current={self.current_serial} (USB={self.usb_serial}, Net={self.network_host})>"

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
