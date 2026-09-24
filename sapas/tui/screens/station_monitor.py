import asyncio
import concurrent.futures
import platform
import re
import socket
import subprocess
import time
from typing import Optional

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from sapas.tui.utils.constants import PASS_SYMBOL, FAIL_SYMBOL


def check_target(
    name: str,
    host: str,
    port: Optional[int] = None,
    timeout: float = 1.5,
) -> dict:
    """Probes a single target via TCP connect (if port specified) or ICMP ping."""
    target_host = host
    check_port = port

    # Auto-extract host:port if not explicitly separated
    if check_port is None and ":" in str(target_host) and not str(target_host).startswith("["):
        parts = str(target_host).split(":")
        target_host = parts[0]
        try:
            check_port = int(parts[1])
        except ValueError:
            pass

    # TCP Port check
    if check_port is not None:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((target_host, int(check_port)), timeout=timeout):
                latency_ms = int(round((time.perf_counter() - t0) * 1000))
                return {
                    "name": name,
                    "host": f"{target_host}:{check_port}",
                    "online": True,
                    "latency": f"{max(1, latency_ms)} ms",
                }
        except (socket.timeout, OSError):
            return {
                "name": name,
                "host": f"{target_host}:{check_port}",
                "online": False,
                "latency": "---",
            }

    # ICMP System Ping
    sys_name = platform.system().lower()
    param_n = "-n" if sys_name == "windows" else "-c"
    param_w = "-w" if sys_name == "windows" else "-W"
    timeout_val = str(int(timeout * 1000)) if sys_name == "windows" else str(max(1, int(timeout)))
    cmd = ["ping", param_n, "1", param_w, timeout_val, target_host]

    t0 = time.perf_counter()
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout + 0.5)
        latency_wall = int(round((time.perf_counter() - t0) * 1000))
        out = res.stdout.lower()

        if res.returncode != 0 or "unreachable" in out or "timed out" in out or "100% loss" in out:
            return {
                "name": name,
                "host": target_host,
                "online": False,
                "latency": "---",
            }

        # Try to parse exact ping latency reported by system ping
        m = re.search(r"time[=<]\s*(\d+)\s*ms", res.stdout, re.IGNORECASE)
        if not m:
            m = re.search(r"時間[=<]\s*(\d+)\s*ms", res.stdout)

        if m:
            val = m.group(1)
            latency_str = "<1 ms" if val == "0" or "time<" in res.stdout.lower() else f"{val} ms"
        else:
            latency_str = f"{max(1, latency_wall)} ms"

        return {
            "name": name,
            "host": target_host,
            "online": True,
            "latency": latency_str,
        }
    except Exception:
        return {
            "name": name,
            "host": target_host,
            "online": False,
            "latency": "---",
        }


class StationMonitorScreen(ModalScreen[None]):
    """Modal screen displaying real-time connectivity status for MONITOR targets defined in station.yaml."""

    REFRESH_INTERVAL: int = 3

    BINDINGS = [
        ("escape", "dismiss_screen", "Close"),
        ("f6", "dismiss_screen", "Close"),
        ("f5", "refresh_targets_manual", "Refresh"),
    ]

    def __init__(self, context=None) -> None:
        super().__init__()
        self.context = context
        self._tick_timer = None
        self._countdown: int = self.REFRESH_INTERVAL
        self._is_probing: bool = False
        self._summary_text: str = ""
        self._summary_color: str = "yellow"

    def _extract_monitor_targets(self) -> list[dict]:
        """Extracts and normalizes the MONITOR section from context / station.yaml."""
        raw_monitor = None
        if self.context:
            raw_monitor = self.context.get("MONITOR")

        targets = []
        if not raw_monitor:
            return targets

        if isinstance(raw_monitor, list):
            for idx, entry in enumerate(raw_monitor, 1):
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("title") or entry.get("host") or f"Target #{idx}"
                    host = entry.get("host") or entry.get("ip") or ""
                    port = entry.get("port")
                    if host:
                        targets.append({"name": str(name), "host": str(host), "port": port})
                elif isinstance(entry, str) and entry.strip():
                    targets.append({"name": entry.strip(), "host": entry.strip(), "port": None})
        elif isinstance(raw_monitor, dict):
            for key, val in raw_monitor.items():
                if isinstance(val, dict):
                    name = val.get("name") or str(key)
                    host = val.get("host") or val.get("ip") or ""
                    port = val.get("port")
                    if host:
                        targets.append({"name": str(name), "host": str(host), "port": port})
                elif isinstance(val, str) and val.strip():
                    targets.append({"name": str(key), "host": val.strip(), "port": None})

        return targets

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🌐 STATION ENVIRONMENT MONITOR", id="station-monitor-title"),
            DataTable(id="station-monitor-table"),
            Static("Probing environment targets... please wait", id="station-monitor-status"),
            Container(
                Button("Close (Esc)", variant="error", id="monitor-btn-close"),
                id="station-monitor-actions",
            ),
            id="station-monitor-dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one("#station-monitor-table", DataTable)
        table.cursor_type = "none"
        table.show_cursor = False
        table.add_column("Target Name", width=26, key="name")
        table.add_column("Host / Address", width=22, key="host")
        table.add_column("Status", width=14, key="status")
        table.add_column("Latency", width=12, key="latency")

        self.action_refresh_targets()
        self._tick_timer = self.set_interval(1.0, self._on_tick)

    def _on_tick(self) -> None:
        """Called every second to update countdown and trigger probe when ready."""
        if self._is_probing or not self._summary_text:
            return

        self._countdown -= 1
        status_label = self.query_one("#station-monitor-status", Static)
        if self._countdown <= 0:
            self._countdown = self.REFRESH_INTERVAL
            self.action_refresh_targets()
        else:
            status_label.update(f"{self._summary_text}  •  Refreshing in {self._countdown}s")
            status_label.styles.color = self._summary_color

    def on_unmount(self) -> None:
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None

    def action_dismiss_screen(self) -> None:
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None
        self.dismiss()

    @on(Button.Pressed, "#monitor-btn-close")
    def on_close_pressed(self) -> None:
        self.action_dismiss_screen()

    def action_refresh_targets_manual(self) -> None:
        """Triggered by F5 shortcut: resets countdown and checks targets immediately."""
        self._countdown = self.REFRESH_INTERVAL
        self.action_refresh_targets()

    @work(exclusive=True)
    async def action_refresh_targets(self) -> None:
        """Pings all configured MONITOR targets concurrently and updates the table."""
        self._is_probing = True
        status_label = self.query_one("#station-monitor-status", Static)
        table = self.query_one("#station-monitor-table", DataTable)

        targets = self._extract_monitor_targets()

        if not targets:
            table.clear()
            self._summary_text = "No MONITOR targets configured in station.yaml"
            self._summary_color = "yellow"
            status_label.update(self._summary_text)
            status_label.styles.color = self._summary_color
            table.add_row(
                Text("(No Targets)", style="italic dim"),
                Text("Define MONITOR: in station.yaml", style="italic dim"),
                Text("---", style="dim"),
                Text("---", style="dim"),
            )
            self._is_probing = False
            return

        # Initialize rows if not yet populated or count changed
        if table.row_count != len(targets):
            table.clear()
            for idx, t in enumerate(targets):
                table.add_row(
                    t["name"],
                    t["host"],
                    Text("⏳ CHECKING", style="bold yellow"),
                    Text("...", style="dim"),
                    key=f"target_{idx}",
                )

        if not self._summary_text:
            status_label.update(f"Probing {len(targets)} environment target(s)... please wait")
            status_label.styles.color = "yellow"

        # Run probes concurrently in background threads
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(targets), 8)) as pool:
            tasks = [
                loop.run_in_executor(
                    pool,
                    check_target,
                    t["name"],
                    t["host"],
                    t.get("port"),
                    1.5,
                )
                for t in targets
            ]
            results = await asyncio.gather(*tasks)

        online_count = 0
        for idx, r in enumerate(results):
            row_key = f"target_{idx}"
            if r["online"]:
                online_count += 1
                status_text = Text(f"{PASS_SYMBOL} ONLINE", style="bold green")
                latency_text = Text(r["latency"], style="green")
            else:
                status_text = Text(f"{FAIL_SYMBOL} OFFLINE", style="bold red")
                latency_text = Text("---", style="dim")

            table.update_cell(row_key, "status", status_text)
            table.update_cell(row_key, "latency", latency_text)

        total = len(targets)
        if online_count == total:
            self._summary_text = f"All {total} targets ONLINE"
            self._summary_color = "green"
        else:
            offline_count = total - online_count
            self._summary_text = f"ALERT: {offline_count} of {total} targets OFFLINE"
            self._summary_color = "red"

        self._countdown = self.REFRESH_INTERVAL
        status_label.update(f"{self._summary_text}  •  Refreshing in {self._countdown}s")
        status_label.styles.color = self._summary_color
        self._is_probing = False
