from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class QuitConfirmScreen(ModalScreen[bool]):
    """Confirmation dialog used to prevent accidental production stop/exit."""

    AUTO_FOCUS = "#quit-no"

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("n", "cancel", "No"),
        ("y", "confirm", "Yes"),
    ]

    def compose(self) -> ComposeResult:
        yield Grid(
            Static("Exit Sapas TUI Tester?", id="quit-title"),
            Static("Current test will stop after the active item completes.", id="quit-message"),
            Static("", classes="quit-spacer"),
            Button("Yes", variant="error", id="quit-yes"),
            Static("", classes="quit-spacer"),
            Button("No", variant="primary", id="quit-no"),
            Static("", classes="quit-spacer"),
            id="quit-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "quit-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
