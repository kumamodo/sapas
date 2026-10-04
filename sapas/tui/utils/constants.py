from rich.text import Text

# Global Unicode Status Symbols matching standard visual weights
PASS_SYMBOL = "\u2713"
FAIL_SYMBOL = "\u274c"

# Structural flow control markers that do not map to physical execution steps
SKIP_FLOW_COMMANDS = {"cycle", "if", "else", "end_if"}


def format_status(status: str) -> Text:
    """Generates padded Rich Text tokens for side-panel menu item statuses."""
    cells = {
        "PENDING": ("PENDING", "dim"),
        "RUNNING": ("RUNNING", "bold yellow"),
        "PASS": (f"{PASS_SYMBOL} PASS", "bold green"),
        "FAIL": (f"{FAIL_SYMBOL} FAIL", "bold red"),
        "SKIP": ("- SKIP", "cyan"),
        "STOP": ("STOP", "bold red"),
        "IF": ("", ""),
        "ELSE": ("", ""),
        "END_IF": ("", ""),
    }
    value, style = cells.get(status, (status, "dim"))
    return Text(value, style=style, no_wrap=True)


def get_default_step_status(step) -> str:
    """Determines the default initial status for a step in the TUI table."""
    cmd = getattr(step, "command", "")
    if cmd == "end_if":
        return "END_IF"
    if cmd == "else":
        return "ELSE"
    if getattr(step, "is_condition", False):
        return "IF"
    return "PENDING"

