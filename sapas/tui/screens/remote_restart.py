"""Modal dialog notifying on-site operator that remote maintenance has ended and requesting app restart."""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class RemoteRestartScreen(ModalScreen[None]):
    """Modal dialog displayed on local station when remote maintenance ends, prompting operator to restart."""

    AUTO_FOCUS = "#restart-confirm-btn"

    BINDINGS = [
        ("enter", "confirm", "Acknowledge & Exit"),
        ("space", "confirm", "Acknowledge & Exit"),
    ]

    def __init__(self, lock_info: dict | None = None) -> None:
        super().__init__()
        self.lock_info = lock_info or {}

    def compose(self) -> ComposeResult:
        ip = self.lock_info.get("ip", "Remote engineer")
        yield Container(
            Static("🔧  REMOTE MAINTENANCE FINISHED  🔧", id="restart-dialog-title"),
            Static(
                f"• Remote maintenance session by {ip} has been released.\n"
                "• Test scripts and station configurations may have been updated.",
                id="restart-dialog-bullets",
            ),
            Static(
                "To ensure the latest test standards take effect,\n"
                "please close and relaunch this application.",
                id="restart-dialog-prompt",
            ),
            Horizontal(
                Button("Acknowledge & Exit (Enter)", variant="success", id="restart-confirm-btn"),
                id="restart-dialog-actions",
            ),
            id="restart-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_confirm()

    def action_confirm(self) -> None:
        self.app.exit()
