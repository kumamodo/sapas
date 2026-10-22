import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from sapas.guard.lock_manager import is_pid_alive
from sapas.trigger.constants import (
    ACTION_START,
    ACTION_STATUS,
    ACTION_STOP,
    STATUS_BLOCKED,
    STATUS_BUSY,
    STATUS_ERROR,
    STATUS_OK,
    TUI_IPC_FILE,
)


class TriggerServer:
    """Lightweight localhost loopback IPC server hosted by active Sapas TUI sessions."""

    def __init__(
        self,
        action_handler: Optional[Callable[[str, dict[str, Any]], dict[str, Any]]] = None,
        handler: Optional[Callable[[str, dict[str, Any]], dict[str, Any]]] = None,
    ) -> None:
        actual_handler = action_handler or handler
        if actual_handler is None:
            raise ValueError("An action handler callback must be provided to TriggerServer.")
        self.action_handler = actual_handler
        self._server_sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.port: int = 0
        self.pid: int = os.getpid()

    def start(self) -> int:
        """Binds to an ephemeral localhost port and registers the TUI IPC record."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", 0))
        self.port = self._server_sock.getsockname()[1]
        self._server_sock.listen(5)
        self._running = True

        # Ensure directory exists and write IPC file atomically
        TUI_IPC_FILE.parent.mkdir(parents=True, exist_ok=True)
        ipc_data = {
            "pid": self.pid,
            "port": self.port,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        temp_file = TUI_IPC_FILE.with_suffix(".tmp")
        temp_file.write_text(json.dumps(ipc_data, indent=2), encoding="utf-8")
        temp_file.replace(TUI_IPC_FILE)

        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="SapasTriggerServer")
        self._thread.start()
        return self.port

    def _listen_loop(self) -> None:
        while self._running and self._server_sock:
            try:
                client_sock, _ = self._server_sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except OSError:
                break

    def _handle_client(self, client_sock: socket.socket) -> None:
        try:
            client_sock.settimeout(3.0)
            data = client_sock.recv(4096).decode("utf-8").strip()
            if not data:
                return

            try:
                request = json.loads(data)
                action = request.get("action", "")
                payload = request.get("payload", {})
                if not action and "sn" in request:
                    action = ACTION_START
                    payload = {"sn": request.get("sn", "")}
            except json.JSONDecodeError:
                # Fallback for plain text triggers like "START" or "SM"
                action = data.lower()
                payload = {}

            # Execute action callback
            try:
                response = self.action_handler(action, payload)
            except Exception as e:
                response = {"status": STATUS_ERROR, "message": f"Handler exception: {e}"}

            resp_json = json.dumps(response) + "\n"
            client_sock.sendall(resp_json.encode("utf-8"))
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass

    def stop(self) -> None:
        """Shuts down the server socket and removes the IPC registration."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        # Clean up IPC file if it belongs to this process
        try:
            if TUI_IPC_FILE.exists():
                data = json.loads(TUI_IPC_FILE.read_text(encoding="utf-8"))
                if data.get("pid") == self.pid:
                    TUI_IPC_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def get_tui_ipc_data() -> Optional[dict[str, Any]]:
    """Returns the active TUI session metadata if currently running."""
    if not TUI_IPC_FILE.exists():
        return None
    try:
        data = json.loads(TUI_IPC_FILE.read_text(encoding="utf-8"))
        pid = data.get("pid", 0)
        port = data.get("port", 0)
        if not is_pid_alive(pid) or port <= 0:
            # Stale IPC file from unexpected crash
            TUI_IPC_FILE.unlink(missing_ok=True)
            return None
        return data
    except Exception:
        return None


def send_trigger(action: str, sn: str = "", timeout: float = 3.0) -> dict[str, Any]:
    """Sends a trigger command to the active Sapas TUI session."""
    ipc_data = get_tui_ipc_data()
    if not ipc_data:
        return {
            "status": STATUS_ERROR,
            "message": "NO_ACTIVE_TUI_SESSION",
            "detail": "No active Sapas TUI dashboard detected on this workstation.",
        }

    port = ipc_data["port"]
    pid = ipc_data["pid"]

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("127.0.0.1", port))

        ssh_client = os.environ.get("SSH_CLIENT", "")
        ssh_conn = os.environ.get("SSH_CONNECTION", "")
        is_ssh = bool(ssh_client or ssh_conn)
        client_ip = ssh_client.split()[0] if ssh_client else ("127.0.0.1" if not is_ssh else "Remote SSH")

        req_data = {
            "action": action,
            "payload": {
                "sn": sn,
                "timestamp": datetime.now().isoformat(),
                "caller": {
                    "is_ssh": is_ssh,
                    "ip": client_ip,
                    "pid": os.getpid(),
                },
            },
        }
        sock.sendall((json.dumps(req_data) + "\n").encode("utf-8"))

        raw_resp = sock.recv(4096).decode("utf-8").strip()
        sock.close()
        if not raw_resp:
            return {"status": STATUS_ERROR, "message": "EMPTY_RESPONSE", "pid": pid}

        resp = json.loads(raw_resp)
        resp["pid"] = pid
        return resp
    except socket.timeout:
        return {
            "status": STATUS_ERROR,
            "message": "SOCKET_TIMEOUT",
            "detail": f"Timed out waiting for response from Sapas TUI (PID {pid}).",
            "pid": pid,
        }
    except Exception as e:
        return {
            "status": STATUS_ERROR,
            "message": "CONNECTION_FAILED",
            "detail": f"Failed to connect to Sapas TUI on port {port}: {e}",
            "pid": pid,
        }


class TriggerClient:
    """Client class to interact with an active Sapas TUI session."""

    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout

    def is_server_available(self) -> bool:
        return get_tui_ipc_data() is not None

    def get_server_info(self) -> Optional[dict[str, Any]]:
        return get_tui_ipc_data()

    def send_command(self, action: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        sn = (payload or {}).get("sn", "") if isinstance(payload, dict) else ""
        return send_trigger(action, sn=sn, timeout=self.timeout)

    def start(self, sn: str = "") -> dict[str, Any]:
        return send_trigger(ACTION_START, sn=sn, timeout=self.timeout)

    def stop(self) -> dict[str, Any]:
        return send_trigger(ACTION_STOP, timeout=self.timeout)

    def status(self) -> dict[str, Any]:
        return send_trigger(ACTION_STATUS, timeout=self.timeout)
