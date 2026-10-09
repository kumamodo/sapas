"""Constants and configuration paths for Sapas Station Guard."""
from pathlib import Path
import os

# Base directory for Sapas global state
DEFAULT_SAPAS_DIR = Path.home() / ".sapas"
LOCK_FILE_PATH = Path(os.environ.get("SAPAS_LOCK_PATH", DEFAULT_SAPAS_DIR / "station.lock"))
GUARD_PID_FILE = DEFAULT_SAPAS_DIR / "guard.pid"

# Default messages and labels
DEFAULT_LOCK_MESSAGE = "Remote engineer maintenance"
STARTUP_SCRIPT_NAME = "sapas_station_guard.vbs"
