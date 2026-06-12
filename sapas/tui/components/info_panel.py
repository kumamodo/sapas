from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Button, Input, Static


class InfoPanel(Container):
    """The top row information panel containing metadata, error codes, timers, and input controls."""

    def compose(self) -> ComposeResult:
        info_box = Container(
            Static("Loading...", id="info-value", classes="box-value"),
            classes="top-box",
            id="info-box",
        )
        error_box = Container(
            Static("", id="error-code", classes="box-value"),
            classes="top-box",
            id="error-box",
        )
        elapsed_box = Container(
            Static("00:00:00.00", id="elapsed-time", classes="box-value"),
            classes="top-box",
            id="elapsed-box",
        )
        serial_box = Container(
            Input(placeholder="sapas1234567890", id="serial-input"),
            Button("Start", id="start-button"),
            classes="top-box",
            id="serial-box",
        )

        info_box.border_title = "Information"
        error_box.border_title = "Error Code"
        elapsed_box.border_title = "Elapsed Time"
        serial_box.border_title = "Serial Number"

        yield info_box
        yield error_box
        yield elapsed_box
        yield serial_box
