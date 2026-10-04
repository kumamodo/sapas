from textual.widgets import DataTable

from sapas.tui.utils.constants import format_status, get_default_step_status
from sapas.tui.utils.data_types import TestStep


class StepsTable(DataTable):
    """Component managing the display and status updates of test sequence steps."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.fixed_columns = 2
        self.step_skip_reasons: dict[str, str] = {}

    def set_skip_reason(self, row_key: str, reason: str) -> None:
        """Associates a specific condition or explanation with a skipped step row."""
        self.step_skip_reasons[row_key] = reason or "Condition evaluated to False"

    def get_skip_reason(self, row_key: str) -> str | None:
        """Retrieves cached skip explanation for a row if available."""
        return self.step_skip_reasons.get(row_key)

    def clear_skip_reasons(self) -> None:
        """Clears cached skip explanations across test cycles."""
        self.step_skip_reasons.clear()

    def on_mount(self) -> None:
        self.add_column("ID", key="id")
        self.add_column("Status", key="status")
        self.add_column("Items", key="item")

    def render_steps(
        self,
        test_steps: list[TestStep],
        step_status: dict[str, str],
        on_fail_steps: list[TestStep] | None = None,
        final_steps: list[TestStep] | None = None,
        is_fail_active: bool = False,
    ) -> None:
        from rich.text import Text

        self.clear()
        for step in test_steps:
            label = step.item_label
            status = step_status.get(step.row_key, get_default_step_status(step))
            self.add_row(step.item_id, format_status(status), label, key=step.row_key)

        if on_fail_steps:
            sep_style = "bold red" if is_fail_active else "dim"
            sep_id = Text("───", style=sep_style)
            sep_status = Text("───────", style=sep_style)
            sep_label = Text("─── ON-FAIL DIAGNOSTICS ───", style=sep_style)
            self.add_row(sep_id, sep_status, sep_label, key="on_fail_separator")

            for step in on_fail_steps:
                label = step.item_label
                status = step_status.get(step.row_key, get_default_step_status(step))
                self.add_row(step.item_id, format_status(status), label, key=step.row_key)

        if final_steps:
            sep_style = "dim"
            sep_id = Text("───", style=sep_style)
            sep_status = Text("───────", style=sep_style)
            sep_label = Text("─── FINAL CLEANUP ───", style=sep_style)
            self.add_row(sep_id, sep_status, sep_label, key="final_separator")

            for step in final_steps:
                label = step.item_label
                status = step_status.get(step.row_key, get_default_step_status(step))
                self.add_row(step.item_id, format_status(status), label, key=step.row_key)

    def highlight_on_fail_separator(self) -> None:
        """Highlights the ON-FAIL header in bold red when failure block is activated."""
        if "on_fail_separator" in self.rows:
            from rich.text import Text
            self.update_cell("on_fail_separator", "id", Text("───", style="bold red"))
            self.update_cell("on_fail_separator", "status", Text("───────", style="bold red"))
            self.update_cell("on_fail_separator", "item", Text("─── ON-FAIL DIAGNOSTICS ───", style="bold red"))

    def reset_on_fail_separator(self) -> None:
        """Resets the ON-FAIL header to dim styling when test cycle resets."""
        if "on_fail_separator" in self.rows:
            from rich.text import Text
            self.update_cell("on_fail_separator", "id", Text("───", style="dim"))
            self.update_cell("on_fail_separator", "status", Text("───────", style="dim"))
            self.update_cell("on_fail_separator", "item", Text("─── ON-FAIL DIAGNOSTICS ───", style="dim"))

    def update_step_status(
        self,
        row_key: str,
        status: str,
        test_steps: list[TestStep],
        step_status: dict[str, str],
        on_fail_steps: list[TestStep] | None = None,
        final_steps: list[TestStep] | None = None,
    ) -> None:
        """Updates internal dictionary keys and triggers state re-renders for test list cells."""
        step_status[row_key] = status
        try:
            # Check if row exists before updating to prevent CellDoesNotExist errors
            if row_key in self.rows:
                self.update_cell(row_key, "status", format_status(status))
                if status in ("RUNNING", "PASS", "FAIL"):
                    try:
                        row_index = self.get_row_index(row_key)
                        region = self._get_row_region(row_index)
                        self.scroll_to_region(region, animate=False)
                    except Exception:
                        pass
            else:
                # Row not found, trigger full refresh
                self.render_steps(test_steps, step_status, on_fail_steps=on_fail_steps, final_steps=final_steps)
        except Exception:
            # Catch-all fallback to ensure the UI continues to function
            self.render_steps(test_steps, step_status, on_fail_steps=on_fail_steps, final_steps=final_steps)
