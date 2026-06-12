from rich.text import Text

# Global Unicode Status Symbols matching standard visual weights
PASS_SYMBOL = "\u2713"
FAIL_SYMBOL = "\u274c"

# Structural flow control markers that do not map to physical execution steps
SKIP_FLOW_COMMANDS = {"cycle", "if", "end_if"}


def format_status(status: str) -> Text:
    """Generates padded Rich Text tokens for side-panel menu item statuses."""
    cells = {
        "PENDING": ("PENDING", "dim"),
        "RUNNING": ("RUNNING", "bold yellow"),
        "PASS": (f"{PASS_SYMBOL} PASS", "bold green"),
        "FAIL": (f"{FAIL_SYMBOL} FAIL", "bold red"),
        "SKIP": ("- SKIP", "cyan"),
    }
    value, style = cells[status]
    return Text(value, style=style, no_wrap=True)
