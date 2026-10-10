"""Lockfile manager for Station Guard."""
import os
import sys
import json
import ctypes
from datetime import datetime
from pathlib import Path
from sapas.guard.constants import LOCK_FILE_PATH, DEFAULT_LOCK_MESSAGE


def get_client_ip() -> str:
    """Extracts remote client IP from OpenSSH environment variables, or falls back to Localhost."""
    ssh_client = os.environ.get("SSH_CLIENT", "")
    if ssh_client.strip():
        parts = ssh_client.strip().split()
        if parts:
            return parts[0]
            
    ssh_conn = os.environ.get("SSH_CONNECTION", "")
    if ssh_conn.strip():
        parts = ssh_conn.strip().split()
        if parts:
            return parts[0]
            
    return "Localhost"


def is_pid_alive(pid: int) -> bool:
    """Checks whether a process ID is currently alive on Windows."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        process_query_limited_info = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_info, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == 259  # STILL_ACTIVE
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock(message: str | None = None) -> dict:
    """Creates the .station_lock file with session metadata."""
    LOCK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    clear_override_event()
    
    clean_msg = (message or "").strip() or DEFAULT_LOCK_MESSAGE
    data = {
        "locked": True,
        "message": clean_msg,
        "ip": get_client_ip(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # Write atomically via temporary file
    temp_file = LOCK_FILE_PATH.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(LOCK_FILE_PATH)
    return data


def release_lock() -> bool:
    """Removes the .station_lock file if present."""
    if LOCK_FILE_PATH.exists():
        try:
            LOCK_FILE_PATH.unlink()
            return True
        except OSError:
            return False
    return False


def record_override_event(reason: str = "On-site Supervisor Key Sequence Override") -> dict:
    """Records an on-site emergency override event and releases lock."""
    from sapas.guard.constants import OVERRIDE_EVENT_FILE
    lock_data = get_lock_data() or {}
    OVERRIDE_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    event_data = {
        "event": "ON_SITE_OVERRIDE",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason,
        "original_lock": lock_data,
    }
    try:
        temp_file = OVERRIDE_EVENT_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(event_data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_file.replace(OVERRIDE_EVENT_FILE)
    except Exception:
        pass
    release_lock()
    return event_data


def get_override_event() -> dict | None:
    """Reads active override event if present."""
    from sapas.guard.constants import OVERRIDE_EVENT_FILE
    if not OVERRIDE_EVENT_FILE.exists():
        return None
    try:
        data = json.loads(OVERRIDE_EVENT_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("event") == "ON_SITE_OVERRIDE":
            return data
    except Exception:
        pass
    return None


def clear_override_event() -> bool:
    """Clears any recorded override event."""
    from sapas.guard.constants import OVERRIDE_EVENT_FILE
    if OVERRIDE_EVENT_FILE.exists():
        try:
            OVERRIDE_EVENT_FILE.unlink()
            return True
        except OSError:
            return False
    return False



def get_lock_data() -> dict | None:
    """Reads and parses the active .station_lock file, or returns None if absent/invalid."""
    if not LOCK_FILE_PATH.exists():
        return None
    try:
        content = LOCK_FILE_PATH.read_text(encoding="utf-8")
        data = json.loads(content)
        if isinstance(data, dict) and data.get("locked"):
            return data
    except Exception:
        pass
    return None


def is_locked() -> bool:
    """Returns True if station is currently locked."""
    return get_lock_data() is not None


def ensure_remote_guard_lock(custom_msg: str | None = None) -> dict | None:
    """If running in a remote SSH session and station is not locked, automatically engage Station Guard.

    Returns the created lock data dict if auto-lock was triggered, or None otherwise.
    """
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_CONNECTION"):
        if not is_locked():
            ip = get_client_ip()
            msg = custom_msg or f"Auto-locked for remote execution by {ip}"
            return acquire_lock(msg)
    return None
