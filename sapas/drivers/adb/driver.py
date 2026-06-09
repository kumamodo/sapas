import subprocess
import logging
from sapas.modules.log import info, error, log

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

    def connect(self):
        """Attempts to connect to the device, prioritizing USB then Network."""
        if self.is_alive():
            return

        # Priority 1: Physical USB
        if self.usb_serial:
            if self._check_device(self.usb_serial):
                self.current_serial = self.usb_serial
                self._connected = True
                info(f"Connected to ADB device via USB [{self.usb_serial}]", tag='ADB')
                return

        # Priority 2: Network (Fallback)
        if self.network_host:
            info(f"USB device [{self.usb_serial}] not found. Attempting Network connection to [{self.network_host}]", tag='ADB')
            # Try to connect via TCP/IP
            try:
                connect_result = self._run_adb(['connect', self.network_host])
                if "connected to" in connect_result.stdout.lower() or self._check_device(self.network_host):
                    self.current_serial = self.network_host
                    self._connected = True
                    info(f"Connected to ADB device via Network [{self.network_host}]", tag='ADB')
                    return
            except Exception as e:
                error(f"Network connection attempt failed: {e}", tag='ADB')

        self._connected = False
        self.current_serial = None
        err_msg = f"Failed to connect to ADB device (USB: {self.usb_serial}, Network: {self.network_host})"
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
