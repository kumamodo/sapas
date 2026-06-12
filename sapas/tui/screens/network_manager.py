from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Static, DataTable
from textual import work, on
from rich.text import Text
import subprocess
import json
import sys

class NetworkManagerScreen(ModalScreen[None]):
    """Modal screen displaying system Network Adapters, IP addresses, and link status."""

    BINDINGS = [
        ("escape", "dismiss_screen", "Close"),
        ("f6", "dismiss_screen", "Close"),
        ("f5", "refresh_adapters", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("🌐 NETWORK ADAPTER MANAGER", id="net-manager-title"),
            DataTable(id="net-manager-table"),
            Static("Scanning network adapters... please wait", id="net-manager-status"),
            Container(
                Button("Refresh (F5)", variant="primary", id="net-btn-refresh"),
                Button("Close (Esc)", variant="error", id="net-btn-close"),
                id="net-manager-actions"
            ),
            id="net-manager-dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one("#net-manager-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Adapter Name", width=32, key="name")
        table.add_column("IP Address", width=18, key="ip")
        table.add_column("Link Speed", width=15, key="speed")
        table.add_column("Status", width=15, key="status")
        
        # Trigger background scan on mount
        self.action_refresh_adapters()

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#net-btn-close")
    def on_close_pressed(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#net-btn-refresh")
    def on_refresh_pressed(self) -> None:
        self.action_refresh_adapters()

    @work(exclusive=True)
    async def action_refresh_adapters(self) -> None:
        """Triggers scanning on background worker and updates UI with the results."""
        status_label = self.query_one("#net-manager-status", Static)
        status_label.update("Scanning network adapters... please wait")
        status_label.styles.color = "yellow"
        
        # Disable buttons during scan to prevent race conditions
        self.query_one("#net-btn-refresh", Button).disabled = True
        self.query_one("#net-btn-close", Button).disabled = True
        
        try:
            worker = self.scan_adapters()
            adapters = await worker.wait()
            self.update_table(adapters)
        except Exception as e:
            status_label.update(f"Scan failed: {e}")
            status_label.styles.color = "red"
        finally:
            self.query_one("#net-btn-refresh", Button).disabled = False
            self.query_one("#net-btn-close", Button).disabled = False

    @work(thread=True)
    def scan_adapters(self) -> list:
        """Synchronous scanning function run in a background thread."""
        ps_command = (
            "Get-NetAdapter | ForEach-Object { "
            "$ip = (Get-NetIPAddress -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress; "
            "[PSCustomObject]@{ "
            "Name = $_.Name; "
            "Description = $_.InterfaceDescription; "
            "Status = $_.Status; "
            "LinkSpeed = $_.LinkSpeed; "
            "IPAddress = if ($ip) { $ip -join ', ' } else { '-' }; "
            "MacAddress = $_.MacAddress "
            "} "
            "} | ConvertTo-Json"
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
                
            adapters = []
            for item in data:
                adapters.append({
                    "name": item.get("Name") or "Unknown Adapter",
                    "description": item.get("Description") or "",
                    "status": item.get("Status") or "Unknown",
                    "speed": item.get("LinkSpeed") or "-",
                    "ip": item.get("IPAddress") or "-",
                })
            
            # Sort active adapters (Up) to the top
            def sort_key(ad):
                return (0 if ad["status"].lower() == "up" else 1, ad["name"])
                
            adapters.sort(key=sort_key)
            return adapters
        except Exception:
            return []

    def update_table(self, adapters: list) -> None:
        """Populates the DataTable with the retrieved adapters."""
        table = self.query_one("#net-manager-table", DataTable)
        table.clear()
        
        for idx, ad in enumerate(adapters):
            name = ad["name"]
            ip = ad["ip"]
            speed = ad["speed"]
            status = ad["status"]
            
            # Highlight Active 'Up' connections in Green/Cyan
            if status.lower() == "up":
                name_cell = Text(name, style="green bold")
                ip_cell = Text(ip, style="green bold")
                speed_cell = Text(speed, style="green bold")
                status_cell = Text(status, style="green bold")
            elif status.lower() == "disconnected":
                name_cell = Text(name, style="dim")
                ip_cell = Text(ip, style="dim")
                speed_cell = Text(speed, style="dim")
                status_cell = Text(status, style="yellow")
            else:
                name_cell = Text(name, style="dim")
                ip_cell = Text(ip, style="dim")
                speed_cell = Text(speed, style="dim")
                status_cell = Text(status, style="red")
                
            table.add_row(name_cell, ip_cell, speed_cell, status_cell, key=f"row_{idx}")
            
        status_label = self.query_one("#net-manager-status", Static)
        active_count = sum(1 for ad in adapters if ad["status"].lower() == "up")
        status_label.update(f"Scan complete. Found {len(adapters)} adapters ({active_count} active).")
        status_label.styles.color = "green"
