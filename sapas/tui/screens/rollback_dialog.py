from pathlib import Path
from typing import Callable, Optional

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class RollbackConfirmScreen(ModalScreen[Optional[bool]]):
    """Safety interlock confirmation modal displayed when exiting Debug Mode with modified files."""

    BINDINGS = [
        ("k", "choose_keep", "Keep"),
        ("r", "choose_revert", "Revert"),
        ("escape", "cancel_exit", "Cancel"),
    ]

    def __init__(
        self,
        modified_files: list[Path],
        on_decision: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__()
        self.modified_files = modified_files
        self.on_decision = on_decision

    def compose(self) -> ComposeResult:
        files_text = "\n".join(f"• {p.name}  ({p.parent.name}/{p.name})" for p in self.modified_files)

        hint_text = Text()
        hint_text.append("Press ", style="italic dim")
        hint_text.append("[Esc]", style="bold yellow")
        hint_text.append(" to cancel and stay in Debug Mode", style="italic dim")

        yield Container(
            Static("⚠️  DEBUG MODIFICATIONS DETECTED", id="rollback-dialog-title"),
            Static(
                "During this debug session, the following file(s) were modified:\n\n"
                f"{files_text}\n\n"
                "Please choose an action before exiting Debug Mode:",
                id="rollback-dialog-message",
            ),
            Container(
                Button("Keep Changes (k)", variant="success", id="btn-keep-changes"),
                Button("Revert to Original (r)", variant="error", id="btn-revert-changes"),
                id="rollback-dialog-actions",
            ),
            Static(hint_text, id="rollback-dialog-hint"),
            id="rollback-dialog-container",
        )

    def on_mount(self) -> None:
        # Default focus to Keep Changes button for convenience
        try:
            self.query_one("#btn-keep-changes", Button).focus()
        except Exception:
            pass

    def action_choose_keep(self) -> None:
        self._finish_decision(True)

    def action_choose_revert(self) -> None:
        self._finish_decision(False)

    def action_cancel_exit(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-keep-changes")
    def on_keep_pressed(self) -> None:
        self._finish_decision(True)

    @on(Button.Pressed, "#btn-revert-changes")
    def on_revert_pressed(self) -> None:
        self._finish_decision(False)

    def _finish_decision(self, keep: bool) -> None:
        if self.on_decision is not None:
            self.on_decision(keep)
        self.dismiss(keep)
