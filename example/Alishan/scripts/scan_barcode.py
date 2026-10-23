import time
import uuid
import sapas
from sapas import TestItem


@sapas.param("--port", type=str, default="", help="Serial COM port for physical barcode scanner (e.g. COM3 or /dev/ttyUSB0)")
@sapas.param("--baud", type=int, default=9600, help="Baud rate for scanner connection")
@sapas.param("--mock", type=str, default="", help="Mock serial number for simulation or offline development")
@sapas.param("--timeout", type=float, default=3.0, help="Scan timeout in seconds")
class ScanBarcode(TestItem):
    """
    [Production Barcode Scanner TestItem]
    Reads DUT barcode/serial number from physical barcode scanner (USB COM / RS232)
    or generates a simulated serial number in test environments.
    
    In Lazy SN mode (when test starts without an upfront SN), dynamically binds 
    the serial number to Sapas runtime via `sapas.var.set("SERIAL_NUMBER", sn)`,
    which rebinds the test output directory from temporary (_TEMP_*) to output/<SN>/<timestamp>/
    and updates the Sapas TUI dashboard in real time.
    """

    measure_file = "scan_barcode.txt"
    result_file = "scan_barcode_result.csv"
    criteria_file = "scan_barcode_criteria.csv"
    logs_folder = "SCAN_BARCODE"
    logs_name = "scan_barcode.log"

    def _read_from_physical_scanner(self, port: str, baud: int, timeout: float) -> str:
        """Attempts to read a line from a physical serial barcode scanner."""
        try:
            import serial  # pyserial
            with serial.Serial(port=port, baudrate=baud, timeout=timeout) as ser:
                sapas.info(f"Connected to physical scanner at {port} ({baud} baud), waiting for scan...")
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                return line
        except ImportError:
            sapas.warn("pyserial package not installed; falling back to simulation.")
            return ""
        except Exception as e:
            sapas.warn(f"Failed to read from scanner port {port}: {e}")
            return ""

    def run_test(self):
        port = getattr(sapas.args, "port", "").strip()
        baud = getattr(sapas.args, "baud", 9600)
        mock_sn = getattr(sapas.args, "mock", "").strip()
        timeout = getattr(sapas.args, "timeout", 3.0)

        existing_sn = str(sapas.var.get("SERIAL_NUMBER") or getattr(sapas.args, "serialNumber", "") or "").strip()
        is_placeholder = not existing_sn or existing_sn.startswith("_TEMP_") or existing_sn in ("[SCANNING...]", "WAITING_SN")

        scanned_sn = ""

        # 1. Try reading from hardware scanner if port configured
        if port:
            scanned_sn = self._read_from_physical_scanner(port, baud, timeout)

        # 2. If no hardware scanner or read was empty, fallback:
        if not scanned_sn:
            if mock_sn:
                scanned_sn = mock_sn
                sapas.info(f"Using provided mock serial number: {scanned_sn}")
            elif not is_placeholder:
                # If an explicit serial number was already provided upfront (e.g. sapas trigger start --sn XXX),
                # preserve it instead of generating a new random simulated SN!
                scanned_sn = existing_sn
                sapas.info(f"Using existing upfront serial number: {scanned_sn}")
            else:
                # Generate realistic Alishan factory serial number (e.g. ALS-202610-xxxx)
                short_id = uuid.uuid4().hex[:6].upper()
                scanned_sn = f"ALS-202610-{short_id}"
                sapas.info(f"Hardware scanner not connected; generated simulated SN: {scanned_sn}")

        # 3. Serial Number Binding
        # In Lazy SN mode, calling sapas.var.set('SERIAL_NUMBER', ...) rebinds the Sapas Runner
        # logging directory from _TEMP_* to output/<SN>/<timestamp>/ and refreshes TUI.
        if is_placeholder:
            sapas.var.set("SERIAL_NUMBER", scanned_sn)
            sapas.info(f"[LAZY-SN] Successfully bound active serial number: {scanned_sn}")
        else:
            sapas.info(f"[SN] Upfront serial number active: {scanned_sn}")

        # 4. Save measurement for Shopfloor / MES criteria evaluation
        sapas.measure.BARCODE = scanned_sn
        sapas.info(f"Measurement BARCODE set to '{scanned_sn}'.")
