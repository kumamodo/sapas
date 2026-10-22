from pathlib import Path
import os

DEFAULT_SAPAS_DIR = Path(os.environ.get("SAPAS_DIR", Path.home() / ".sapas"))
TUI_IPC_FILE = Path(os.environ.get("SAPAS_TUI_IPC_FILE", DEFAULT_SAPAS_DIR / "tui.ipc"))

ACTION_START = "start"
ACTION_STOP = "stop"
ACTION_STATUS = "status"

STATUS_OK = "ok"
STATUS_BUSY = "busy"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"
