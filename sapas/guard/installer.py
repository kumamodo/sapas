"""Windows Startup installer and process manager for Sapas Station Guard."""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from sapas.guard.constants import STARTUP_SCRIPT_NAME, GUARD_PID_FILE, DEFAULT_SAPAS_DIR
from sapas.guard.lock_manager import is_pid_alive, is_locked, get_lock_data


def get_startup_dir() -> Path:
    """Returns the Windows Startup folder for the current user."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    startup = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    return startup


def get_pythonw_path() -> str:
    """Locates the pythonw.exe binary for windowless background execution."""
    current_exe = Path(sys.executable)
    sibling_pythonw = current_exe.with_name("pythonw.exe")
    if sibling_pythonw.exists():
        return str(sibling_pythonw)

    found = shutil.which("pythonw")
    if found:
        return found

    return sys.executable


def get_daemon_pid() -> int | None:
    """Returns the active daemon PID if running, else None."""
    if not GUARD_PID_FILE.exists():
        return None
    try:
        pid = int(GUARD_PID_FILE.read_text(encoding="utf-8").strip())
        if is_pid_alive(pid):
            return pid
    except Exception:
        pass
    return None


def start_daemon_process() -> bool:
    """Spawns the Station Guard daemon in background if not already running."""
    active_pid = get_daemon_pid()
    if active_pid:
        return True

    pythonw = get_pythonw_path()
    try:
        # DETACHED_PROCESS flag on Windows for complete detachment from the launching terminal
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [pythonw, "-m", "sapas.guard.daemon"],
            creationflags=creationflags,
            close_fds=True,
        )
        return True
    except Exception as e:
        print(f"[Error] Failed to spawn Station Guard daemon: {e}")
        return False


def stop_daemon_process() -> bool:
    """Terminates the active daemon process if running."""
    active_pid = get_daemon_pid()
    if not active_pid:
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(active_pid)], capture_output=True)
        else:
            os.kill(active_pid, 9)
        if GUARD_PID_FILE.exists():
            GUARD_PID_FILE.unlink()
        return True
    except Exception as e:
        print(f"[Error] Failed to terminate daemon PID {active_pid}: {e}")
        return False


def install() -> bool:
    """Creates startup script in Windows Startup directory and launches daemon."""
    startup_dir = get_startup_dir()
    vbs_path = startup_dir / STARTUP_SCRIPT_NAME
    pythonw = get_pythonw_path()

    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run """{pythonw}"" -m sapas.guard.daemon", 0, False\r\n'
    )

    try:
        vbs_path.write_text(vbs_content, encoding="utf-8")
    except Exception as e:
        print(f"[Error] Failed to write startup script: {e}")
        return False

    # Also start it right away
    start_daemon_process()
    return True


def uninstall() -> bool:
    """Removes startup script and terminates any active daemon."""
    startup_dir = get_startup_dir()
    vbs_path = startup_dir / STARTUP_SCRIPT_NAME
    if vbs_path.exists():
        try:
            vbs_path.unlink()
        except Exception:
            pass

    stop_daemon_process()
    return True


def get_status() -> dict:
    """Returns a dictionary summary of guard status."""
    startup_dir = get_startup_dir()
    vbs_path = startup_dir / STARTUP_SCRIPT_NAME
    daemon_pid = get_daemon_pid()
    lock_info = get_lock_data()

    return {
        "installed": vbs_path.exists(),
        "running": daemon_pid is not None,
        "daemon_pid": daemon_pid,
        "locked": lock_info is not None,
        "lock_info": lock_info,
        "vbs_path": str(vbs_path),
    }
