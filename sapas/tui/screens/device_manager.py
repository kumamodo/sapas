from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Static, DataTable
from textual import work, on
from rich.text import Text
import subprocess
import json
import re
import sys

class DeviceManagerScreen(ModalScreen[None]):
    """Modal screen displaying system COM Ports and USB devices."""

    BINDINGS = [
        ("escape", "dismiss_screen", "Close"),
        ("f4", "dismiss_screen", "Close"),
        ("f5", "refresh_devices", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🔌 SYSTEM DEVICE MANAGER", id="dev-manager-title"),
            DataTable(id="dev-manager-table"),
            Static("Scanning devices... please wait", id="dev-manager-status"),
            Container(
                Button("Refresh (F5)", variant="primary", id="dev-btn-refresh"),
                Button("Close (Esc)", variant="error", id="dev-btn-close"),
                id="dev-manager-actions"
            ),
            id="dev-manager-dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one("#dev-manager-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Device Name", width=42, key="name")
        table.add_column("Port", width=10, key="port")
        table.add_column("Status", width=10, key="status")
        
        # Trigger background scan on mount
        self.action_refresh_devices()

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#dev-btn-close")
    def on_close_pressed(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#dev-btn-refresh")
    def on_refresh_pressed(self) -> None:
        self.action_refresh_devices()

    @work(exclusive=True)
    async def action_refresh_devices(self) -> None:
        """Triggers scanning on background worker and updates UI with the results."""
        status_label = self.query_one("#dev-manager-status", Static)
        status_label.update("Scanning devices... please wait")
        status_label.styles.color = "yellow"
        
        # Disable buttons during scan to prevent race conditions
        self.query_one("#dev-btn-refresh", Button).disabled = True
        self.query_one("#dev-btn-close", Button).disabled = True
        
        try:
            worker = self.scan_devices()
            devices = await worker.wait()
            self.update_table(devices)
        except Exception as e:
            status_label.update(f"Scan failed: {e}")
            status_label.styles.color = "red"
        finally:
            self.query_one("#dev-btn-refresh", Button).disabled = False
            self.query_one("#dev-btn-close", Button).disabled = False

    @work(thread=True)
    def scan_devices(self) -> list:
        """Synchronous scanning function run in a background thread."""
        ps_command = (
            "Get-PnpDevice -PresentOnly | "
            "Where-Object { "
            "$_.Class -eq 'Ports' -or "
            "$_.Class -eq 'USB' -or "
            "$_.Class -like '*DAQ*' -or "
            "$_.Class -like '*National*' -or "
            "$_.Class -like '*Instrument*' -or "
            "$_.Class -like '*GPIB*' "
            "} | "
            "Select-Object -Property FriendlyName, InstanceId, Status, Class | "
            "ConvertTo-Json"
        )
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_command
        ]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=0x08000000 if sys.platform == "win32" else 0,
                timeout=10
            )
            if res.returncode != 0:
                return []
            
            if not res.stdout.strip():
                return []
                
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                data = []
                
            devices = []
            for item in data:
                friendly_name = item.get("FriendlyName") or "Unknown Device"
                status = item.get("Status") or "Unknown"
                
                com_match = re.search(r'\((COM\d+)\)', friendly_name)
                com_port = com_match.group(1) if com_match else None
                
                devices.append({
                    "name": friendly_name,
                    "port": com_port,
                    "status": status
                })
            
            def sort_key(dev):
                if dev["port"]:
                    num_match = re.search(r'\d+', dev["port"])
                    num = int(num_match.group(0)) if num_match else 0
                    return (0, num, dev["name"])
                else:
                    return (1, 0, dev["name"])
                    
            devices.sort(key=sort_key)
            return devices
        except Exception:
            return []

    def update_table(self, devices: list) -> None:
        """Populates the DataTable with the retrieved devices."""
        table = self.query_one("#dev-manager-table", DataTable)
        table.clear()
        
        for idx, dev in enumerate(devices):
            name = dev["name"]
            port = dev["port"] or "-"
            status = dev["status"]
            
            # Highlight COM Ports with Cyan color
            if dev["port"]:
                name_cell = Text(name, style="cyan bold")
                port_cell = Text(port, style="cyan bold")
                status_cell = Text(status, style="green bold" if status == "OK" else "red bold")
            else:
                name_cell = Text(name, style="dim" if "hub" in name.lower() or "controller" in name.lower() else "")
                port_cell = Text(port, style="dim")
                status_cell = Text(status, style="green" if status == "OK" else "red")
                
            table.add_row(name_cell, port_cell, status_cell, key=f"row_{idx}")
            
        status_label = self.query_one("#dev-manager-status", Static)
        com_count = sum(1 for d in devices if d["port"])
        status_label.update(f"Scan complete. Found {len(devices)} devices ({com_count} COM ports).")
        status_label.styles.color = "green"
