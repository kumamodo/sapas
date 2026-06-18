from textual.widgets import DataTable

from sapas.tui.utils.constants import format_status
from sapas.tui.utils.data_types import TestStep


class StepsTable(DataTable):
    """Component managing the display and status updates of test sequence steps."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cursor_type = "none"
        self.zebra_stripes = True
        self.fixed_columns = 2

    def on_mount(self) -> None:
        self.add_column("ID", key="id")
        self.add_column("Status", key="status")
        self.add_column("Items", key="item")

    def render_steps(self, test_steps: list[TestStep], step_status: dict[str, str]) -> None:
        self.clear()
        for step in test_steps:
            label = step.item_label
            status = step_status.get(step.item_id, "PENDING")
            self.add_row(step.item_id, format_status(status), label, key=step.item_id)

    def update_step_status(self, row_key: str, status: str, test_steps: list[TestStep], step_status: dict[str, str]) -> None:
        """Updates internal dictionary keys and triggers state re-renders for test list cells."""
        step_status[row_key] = status
        try:
            # Check if row exists before updating to prevent CellDoesNotExist errors
            if row_key in self.rows:
                self.update_cell(row_key, "status", format_status(status))
                if status == "RUNNING":
                    self.scroll_to_row(row_key)
            else:
                # Row not found, trigger full refresh
                self.render_steps(test_steps, step_status)
        except Exception:
            # Catch-all fallback to ensure the UI continues to function
            self.render_steps(test_steps, step_status)
