from datetime import datetime
from rich.text import Text
from textual.widgets import RichLog


class LogView(RichLog):
    """Component managing log displays and real-time syntax color highlighting."""

    def write_log(self, message: str, style: str = "white") -> None:
        """Applies advanced regular expression highlight parsing to live engine output lines."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = Text(message, style=style)

        # Color core subsystem markers distinctly
        log_text.highlight_regex(r"\[\s*RUNNER\s*\]", "bold #5f87af")
        log_text.highlight_regex(r"\[\s*ACTION\s*\]", "bold #8787af")
        log_text.highlight_regex(r"\[\s*USER\s*\]", "bold #00afaf")
        log_text.highlight_regex(r"\[\s*INFO\s*\]", "bold #5f87af")
        log_text.highlight_regex(r"\[\s*WARN\s*\]", "bold yellow")
        log_text.highlight_regex(r"\[\s*ERROR\s*\]", "bold red")
        log_text.highlight_regex(r"\[\s*SSH\s*\]|\[\s*SFTP\s*\]", "bold #af87af")
        log_text.highlight_regex(r"\[\s*STDERR\s*\]", "bold red")
        log_text.highlight_regex(r"\[\s*ITEM\s*\]", "bold #87afd7")
        log_text.highlight_regex(r"\[\s*OUT\s*\]", "bold #d787d7")

        # Identify specific low-level data telemetry dumps
        if message.startswith("##"):
            log_text.style = "yellow"

        # Parse acceptance or rejection strings to match color flags
        if "PASS" in message or "accepted" in message:
            log_text.highlight_regex(r"PASS|Unit accepted\.", "bold green")
        if "FAIL" in message or "Error" in message or "rejected" in message:
            log_text.highlight_regex(r"FAIL|Error[^|]*|Unit rejected\.", "bold red")

        self.write(Text.assemble((timestamp, "dim"), (" | ", "dim"), log_text))
