import asyncio
import contextlib
import signal
import sys
import yaml
from argparse import Namespace
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.events import Resize
from textual.theme import Theme
from textual.widgets import Button, Input, Static, Footer, Header

from sapas.cli import setup_context
from sapas.core.flow_loader import FlowLoader

# Subcomponents & modules
from sapas.tui.components.info_panel import InfoPanel
from sapas.tui.components.steps_table import StepsTable
from sapas.tui.components.log_view import LogView
from sapas.tui.screens.quit_confirm import QuitConfirmScreen
from sapas.tui.screens.device_manager import DeviceManagerScreen
from sapas.tui.screens.network_manager import NetworkManagerScreen
from sapas.tui.utils.constants import PASS_SYMBOL, FAIL_SYMBOL, SKIP_FLOW_COMMANDS
from sapas.tui.utils.data_types import TestStep
from sapas.tui.engine.log_interceptor import LogInterceptor
from sapas.tui.engine.runner_worker import run_flow_in_daemon_thread


sapas_classic_theme = Theme(
    name="sapas-classic",
    primary="#123244",
    secondary="#0E4C70",
    accent="#f2c94c",
    background="#071016",
    foreground="#d9e1e7",
    surface="#081218",
    panel="#0B1C28",
    success="#40c878",
    warning="#f2c94c",
    error="#ff5d5d",
)


class SapasDashboard(App[None]):
    """Factory-grade Sapas production test dashboard built with Textual."""

    AUTO_FOCUS = "#serial-input"
    CSS_PATH = Path(__file__).with_name("dashboard.tcss")
    BINDINGS = [
        ("ctrl+q", "request_quit", "Quit"),
        ("ctrl+c", "request_quit", "Quit"),
        ("f2", "focus_serial", "Serial Number"),
        ("f3", "cycle_theme", "Theme"),
        ("f4", "toggle_device_manager", "Device Manager"),
        ("f6", "toggle_network_manager", "Network Adapters"),
    ]

    def __init__(self, context=None, cli_args=None) -> None:
        super().__init__()
        self.args = cli_args or Namespace(project=None, station=None, test_flow=None, serialNumber="", timeStamp="")
        self.context = context
        self.test_steps: list[TestStep] = []
        self.step_index_by_runner_index: dict[str, str] = {}
        self.pending_step_ids_by_item: dict[str, list[str]] = {}
        self.step_status: dict[str, str] = {}
        self.running_step_key: str | None = None
        self.started_at: datetime | None = None
        self.is_testing = False
        self.stop_requested = False
        self.current_cycle = 1
        self.total_cycles = 1
        self._abort_ui = False
        self._cycle_task: asyncio.Task | None = None
        self._previous_sigint_handler = None
        self._sigint_pending = False

        # Instantiate log parser with callbacks
        self.log_interceptor = LogInterceptor(
            on_cycle_start=self._handle_cycle_start,
            on_step_start=self._handle_step_start,
            on_delay_start=self._handle_delay_start,
            on_step_result=self._handle_step_result,
            on_delay_finish=self._handle_delay_finish,
            on_block_skip=self._handle_block_skip,
        )

    def _handle_context_created(self, context) -> None:
        self.context = context

    def _handle_cycle_start(self, current_cycle: int, total_cycles: int) -> None:
        self.current_cycle = current_cycle
        self.total_cycles = total_cycles
        self.update_info_display()
        self.reset_cycle_view()

    def _handle_step_start(self, runner_index: str) -> None:
        row_key = self.step_index_by_runner_index.get(runner_index)
        if row_key:
            self.running_step_key = row_key
            self.set_step_status(row_key, "RUNNING")

    def _handle_delay_start(self, delay_item: str) -> None:
        row_key = self.pop_next_pending_step(delay_item)
        if row_key:
            self.running_step_key = row_key
            self.set_step_status(row_key, "RUNNING")

    def _handle_step_result(self, item: str, return_code: int) -> None:
        row_key = self.running_step_key or self.pop_next_pending_step(item)
        if row_key:
            self.set_step_status(row_key, "PASS" if return_code == 0 else "FAIL")
            self.running_step_key = None

    def _handle_delay_finish(self) -> None:
        if self.running_step_key:
            self.set_step_status(self.running_step_key, "PASS")
            self.running_step_key = None

    def _handle_block_skip(self) -> None:
        for step in self.test_steps:
            if self.step_status.get(step.item_id) == "PENDING":
                self.set_step_status(step.item_id, "SKIP")
                break

    def compose(self) -> ComposeResult:
        """Constructs the TUI visual tree hierarchy layout."""
        yield Container(
            Header(show_clock=True),
            InfoPanel(id="top-row"),
            Container(
                Container(
                    StepsTable(id="items-table"),
                    id="items-panel"
                ),
                Container(
                    Static("Live Log", id="log-title"),
                    Static("", id="result-banner"),
                    LogView(id="live-log", wrap=True, auto_scroll=True, highlight=False),
                    id="log-panel"
                ),
                id="main-body",
            ),
            Footer(),
            id="app-root",
        )

    async def on_mount(self) -> None:
        """Triggers asynchronous setup routines once screen mounting finishes initialization."""
        self.register_theme(sapas_classic_theme)
        self.theme = "sapas-classic"

        self.install_signal_handlers()
        
        self.setup_dashboard_flow()       
        self.reset_station_view(clear_log=True)
        self.set_interval(0.2, self.update_elapsed)
        self.set_interval(0.1, self.check_signal_quit_request)
        self.set_interval(1, self.toggle_sf_blink)
        self.apply_responsive_layout(self.screen.size.width)
        self.query_one("#live-log", LogView).can_focus = False
        self.call_after_refresh(self.focus_serial_input)

    def toggle_sf_blink(self) -> None:
        """Toggles the blink class on the app root if Shopfloor is disabled."""
        app_root = self.query_one("#app-root")
        if app_root.has_class("sf-disabled"):
            app_root.toggle_class("blink")
        else:
            app_root.remove_class("blink")

    def install_signal_handlers(self) -> None:
        """Route terminal Ctrl+C/SIGINT through the same guarded quit dialog."""
        self._previous_sigint_handler = signal.getsignal(signal.SIGINT)

        def handle_sigint(_signum, _frame) -> None:
            self._sigint_pending = True

        signal.signal(signal.SIGINT, handle_sigint)

    def check_signal_quit_request(self) -> None:
        """Open the quit dialog from Textual's normal UI context after SIGINT."""
        if not self._sigint_pending:
            return
        self._sigint_pending = False
        self.action_request_quit()

    def on_unmount(self) -> None:
        """Restore the previous SIGINT handler when the app is torn down."""
        if self._previous_sigint_handler is not None:
            with contextlib.suppress(Exception):
                signal.signal(signal.SIGINT, self._previous_sigint_handler)

    def setup_dashboard_flow(self) -> None:
        """Parses operational context and resolves exact execution metadata for display fields."""
        if self.context is None:
            return

        # Extract and map executable step identifiers
        self.test_steps, self.total_cycles = self.load_station_steps()
        self.current_cycle = 1
        
        self.update_info_display()
        self.rebuild_step_indexes()

    def update_info_display(self) -> None:
        """Updates the information box with current session metadata."""
        if self.context is None:
            return

        # 1. Extract context strings
        station_name = self.context.get("STATION_NAME", "Unknown")
        project_name = self.context.get("PROJECT_NAME", "Unknown")
        workspace_root = Path(self.context.get("WORKSPACE_ROOT", Path.cwd()))
        
        # 2. Parse version.yaml configuration file dynamically
        ver_path = workspace_root / project_name / "configs" / "version.yaml"
        script_version = "v0.0.0"
        try:
            with open(ver_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                script_version = data.get("version", "v0.0.0")
        except Exception:
            pass

        # 3. Calculate target test flow layout descriptor
        requested_flow = self.args.test_flow or f"{station_name}.flow"

        # 4. Check Shopfloor status
        sf_enabled = self.context.get("ENABLE_SHOPFLOOR", False)
        sf_status = "Enabled" if sf_enabled else "Disabled"
        
        # Apply visual indicator to app root
        app_root = self.query_one("#app-root")
        app_root.remove_class("sf-enabled", "sf-disabled")
        if sf_enabled:
            app_root.add_class("sf-enabled")
            app_root.border_subtitle = " SHOPFLOOR ONLINE "
            app_root.border_title = ""
        else:
            app_root.add_class("sf-disabled")
            app_root.border_subtitle = " SHOPFLOOR OFFLINE "
            app_root.border_title = ""

        # 5. Construct metadata text string using left-aligned factory guidelines
        info_text = (
            f"Station: {station_name}\n"
            f"Script:  {script_version}\n"
            f"Flow:    {requested_flow}"
        )
        self.query_one("#info-value", Static).update(info_text)
        
        # 5. Update header title and sub_title with colors and symbols
        self.title = Text.assemble(("Sapas TUI ", "bold cyan"), ("Tester", "bold"))
        self.sub_title = Text.assemble(
            ("❱❱ ", "bold yellow"),
            (f"Cycle {self.current_cycle}/{self.total_cycles}", "bold yellow"),
            (" ❰❰", "bold yellow")
        )

    def load_station_steps(self) -> tuple[list[TestStep], int]:
        """Loads and filters valid steps from target flow configurations via FlowLoader."""
        if self.context is None:
            return [], 1

        workspace_root = Path(self.context.get("WORKSPACE_ROOT", Path.cwd()))
        project_name = self.context.get("PROJECT_NAME")
        station_name = self.context.get("STATION_NAME")
        requested_flow = self.args.test_flow or f"{station_name}.flow"
        flow_dir = workspace_root / project_name / "flows"
        flow_path = flow_dir / requested_flow

        if not flow_path.exists():
            matches = [path for path in flow_dir.glob("*.flow") if path.name.lower() == requested_flow.lower()]
            if matches:
                flow_path = matches[0]

        cycle_count, flow_items, _ = FlowLoader().load_flow(str(flow_path))
        steps: list[TestStep] = []
        for runner_index, (command, item) in enumerate(flow_items):
            command = command.strip().lower()
            item = item.strip()
            if command in SKIP_FLOW_COMMANDS:
                continue
            item_id = f"{len(steps) + 1:02d}"
            label = f"{command} {item}".strip() if command in ("delay", "prompt") else item
            steps.append(
                TestStep(
                    item_id=item_id,
                    runner_index=f"{runner_index:02d}",
                    item_label=label,
                    flow_item=item,
                    command=command,
                )
            )
        return steps, cycle_count

    def on_resize(self, event: Resize) -> None:
        """Handles screen resizing callbacks dynamically."""
        self.apply_responsive_layout(event.size.width)

    def apply_responsive_layout(self, width: int) -> None:
        """Injects responsive layout classes into screen objects based on cell width metrics."""
        self.screen.set_class(width < 100, "narrow")

    def action_focus_serial(self) -> None:
        """Action handler to focus on the serial number input field."""
        self.focus_serial_input()

    def action_cycle_theme(self) -> None:
        """Cycle through the registered available themes."""
        themes = list(self.available_themes.keys())
        if not themes:
            return
        try:
            current_index = themes.index(self.theme)
        except ValueError:
            current_index = 0
        next_index = (current_index + 1) % len(themes)
        self.theme = themes[next_index]
        self.write_terminal_log(f"[INFO] Theme switched to: {self.theme}")

    def action_request_quit(self) -> None:
        """Ask the operator to confirm before stopping execution and closing the TUI."""
        if any(isinstance(screen, QuitConfirmScreen) for screen in self.screen_stack):
            return
        self.push_screen(QuitConfirmScreen(), self.handle_quit_confirmation)

    def action_toggle_device_manager(self) -> None:
        """Toggle the Device Manager overlay screen."""
        for screen in self.screen_stack:
            if isinstance(screen, DeviceManagerScreen):
                self.pop_screen()
                return
        self.push_screen(DeviceManagerScreen())

    def action_toggle_network_manager(self) -> None:
        """Toggle the Network Adapter Manager overlay screen."""
        for screen in self.screen_stack:
            if isinstance(screen, NetworkManagerScreen):
                self.pop_screen()
                return
        self.push_screen(NetworkManagerScreen())

    def handle_quit_confirmation(self, confirmed: bool) -> None:
        """Handle operator confirmation result from the quit dialog."""
        if confirmed:
            self.stop_and_exit()
        else:
            self.call_after_refresh(self.focus_serial_input)

    def stop_and_exit(self) -> None:
        """Exit after raising a cooperative stop request for any active runner."""
        self._abort_ui = True
        self._request_runner_stop()
        self.exit()

    def _request_runner_stop(self) -> None:
        """Signal the in-process runner to stop without creating external stop files."""
        if self.context is not None:
            self.context.set("STOP_REQUESTED", True)

    def focus_serial_input(self) -> None:
        """Sets cursor focus directly onto the primary interactive text entry component."""
        serial_input = self.query_one("#serial-input", Input)
        if not serial_input.disabled:
            serial_input.focus()

    def reset_station_view(self, *, clear_log: bool) -> None:
        """Wipes terminal panels to bring the view back to a clean standby state."""
        self.started_at = None
        self.running_step_key = None
        self.stop_requested = False
        self.rebuild_step_indexes()
        self.step_status = {step.item_id: "PENDING" for step in self.test_steps}
        self.render_items_list()

        if clear_log:
            self.query_one("#live-log", LogView).clear()
            self.write_log("Station ready. Awaiting Serial Number input.", "dim")

        self.query_one("#error-code", Static).remove_class("fail", "running", "pass", "check")
        self.query_one("#error-code", Static).update("")
        self.query_one("#elapsed-time", Static).update("00:00:00.00")
        self.set_result_banner("")

    def set_error_code(self, value: str, state: str = "") -> None:
        """Updates display contents and shifts background styles on the error status indicator."""
        error_widget = self.query_one("#error-code", Static)
        error_widget.remove_class("fail", "running", "pass", "check")
        if state:
            error_widget.add_class(state)
        error_widget.update(value)

    def render_items_list(self) -> None:
        """Renders out clean alphanumeric step identifiers within the diagnostic item view panel."""
        self.query_one("#items-table", StepsTable).render_steps(self.test_steps, self.step_status)

    def set_step_status(self, row_key: str, status: str) -> None:
        """Updates internal dictionary keys and triggers state re-renders for test list cells."""
        self.query_one("#items-table", StepsTable).update_step_status(row_key, status, self.test_steps, self.step_status)

    def item_lookup_keys(self, item: str) -> list[str]:
        """Returns stable lookup aliases for flow items whose log text may be normalized."""
        keys = [item]
        with contextlib.suppress(ValueError):
            value = float(item)
            for key in (str(value), str(int(value)) if value.is_integer() else None):
                if key is not None and key not in keys:
                    keys.append(key)
        return keys

    def rebuild_step_indexes(self) -> None:
        """Build repeat-safe lookup maps for the current flow display rows."""
        self.step_index_by_runner_index = {}
        self.pending_step_ids_by_item = {}
        for step in self.test_steps:
            self.step_index_by_runner_index[step.runner_index] = step.item_id
            for key in self.item_lookup_keys(step.flow_item):
                self.pending_step_ids_by_item.setdefault(key, []).append(step.item_id)

    def pop_next_pending_step(self, item: str) -> str | None:
        """Returns the next pending row for repeated flow items while preserving execution order."""
        for key in self.item_lookup_keys(item):
            candidates = self.pending_step_ids_by_item.get(key, [])
            while candidates:
                row_key = candidates.pop(0)
                if self.step_status.get(row_key) == "PENDING":
                    return row_key
        return None

    def update_elapsed(self) -> None:
        """Periodic clock callback displaying accurate test execution time deltas."""
        if self.started_at is None or not self.is_testing:
            return
        elapsed = (datetime.now() - self.started_at).total_seconds()
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.query_one("#elapsed-time", Static).update(f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}")

    def write_log(self, message: str, style: str = "") -> None:
        """Applies advanced regular expression highlight parsing to live engine output lines."""
        self.query_one("#live-log", LogView).write_log(message, style)

    def write_terminal_log(self, message: str, style: str = "") -> None:
        """Writes message logs and updates item metrics simultaneously."""
        if self._abort_ui:
            return
        self.log_interceptor.feed_line(message)
        self.write_log(message, style)

    def emit_from_worker(self, message: str, style: str = "") -> None:
        """Safely passes incoming background worker thread messages into the TUI main loop thread."""
        if self._abort_ui:
            return
        self.call_from_thread(self.write_terminal_log, message, style)

    def reset_cycle_view(self) -> None:
        """Resets the UI state for a new cycle within the same test session."""
        self.running_step_key = None
        self.rebuild_step_indexes()
        self.step_status = {step.item_id: "PENDING" for step in self.test_steps}
        self.render_items_list()

        # Reset error code and banner for the new cycle
        error_widget = self.query_one("#error-code", Static)
        error_widget.remove_class("fail", "running", "pass", "check")
        error_widget.update("RUNNING")
        error_widget.add_class("running")
        self.set_result_banner("")

    def set_result_banner(self, result: str) -> None:
        """Toggles layout classes and maps visibility flags for overlay pass/fail result banners."""
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("active", "pass", "fail", "check")
        if not result:
            box = banner
            box.update("")
            return
        banner.add_class("active")
        if result == "PASS":
            banner.add_class("pass")
        elif result == "CHECK":
            banner.add_class("check")
        else:
            banner.add_class("fail")
        banner.update(self.make_result_banner(result))

    def make_result_banner(self, result: str) -> Text:
        """Formats the textual payload string displayed inside overlay banners using Rich Text."""
        sn = getattr(self.args, "serialNumber", "N/A") or "N/A"
        
        if result == "PASS":
            color = "bold green"
            symbol = PASS_SYMBOL
            status_text = "UNIT ACCEPTED"
        elif result == "CHECK":
            color = "bold yellow"
            symbol = "\u26a0"
            status_text = "MANUAL CHECK REQUIRED"
        else:
            color = "bold red"
            symbol = FAIL_SYMBOL
            status_text = "UNIT REJECTED"
        
        res = Text()
        res.append(f"{result}  ", style=color)
        res.append(f"[{sn}]  ", style="bold")
        res.append(f"{symbol}  {status_text}", style=color)
        return res

    @on(Input.Submitted, "#serial-input")
    def on_serial_submitted(self, event: Input.Submitted) -> None:
        """Listens for enter key submissions inside input boxes."""
        self.start_cycle(event.value.strip())

    @on(Button.Pressed, "#start-button")
    def on_start_pressed(self) -> None:
        """Listens for active clicks targeting the primary cycle action button."""
        if self.is_testing:
            self.request_test_stop()
            return
        self.start_cycle(self.query_one("#serial-input", Input).value.strip())

    def request_test_stop(self) -> None:
        """Raise a cooperative stop request while keeping the dashboard open."""
        if self.stop_requested:
            return
        self.stop_requested = True
        if self.context is not None:
            self.context.set("STOP_REQUESTED", True)
        self.set_error_code("STOPPING", "running")
        self.query_one("#start-button", Button).label = "Stopping"
        self.write_terminal_log("Stop requested by operator. Waiting for current item to complete.", "bold yellow")

    def start_cycle(self, serial_number: str) -> None:
        """Validates current state constraints before spawning execution cycles."""
        if self.is_testing or not serial_number:
            self.focus_serial_input()
            return
        self._abort_ui = False
        self._cycle_task = asyncio.create_task(self.run_station_cycle(serial_number))

    async def run_station_cycle(self, serial_number: str) -> None:
        """Core Orchestrator Loop: Executes a full automated production-line cycle flow safely."""
        self.is_testing = True
        self.stop_requested = False
        serial_input = self.query_one("#serial-input", Input)
        start_button = self.query_one("#start-button", Button)
        serial_input.disabled = True
        start_button.disabled = False
        start_button.label = "Stop"

        self.reset_station_view(clear_log=True)
        self.args.serialNumber = serial_number
        self.update_info_display()

        serial_input.value = serial_number
        self.started_at = datetime.now()
        self.set_error_code("RUNNING", "running")
        self.write_terminal_log(f"Serial Number accepted: {serial_number}", "bold")
        self.write_terminal_log("Station interlock engaged. Real Sapas flow started.", "yellow")

        # Offload synchronous execution without blocking Textual's message pump or app shutdown.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            final_status, context = await run_flow_in_daemon_thread(
                args=self.args,
                context=self.context,
                serial_number=serial_number,
                timestamp=timestamp,
                emit_line_cb=self.emit_from_worker,
                stop_requested=self.stop_requested,
                abort_requested_cb=lambda: self._abort_ui,
                call_from_thread_fn=self.call_from_thread,
                on_context_created=self._handle_context_created
            )
        except Exception as e:
            import traceback
            self.write_terminal_log(f"[ERROR] Exception in runner thread: {e}", "bold red")
            self.write_terminal_log(traceback.format_exc(), "bold red")
            final_status = "FAIL"
            context = self.context

        end_time = datetime.now()
        exact_elapsed = (end_time - self.started_at).total_seconds()
        self.is_testing = False
        
        # Guarantee precision updates for terminal clock views upon completion
        hours, remainder = divmod(exact_elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.query_one("#elapsed-time", Static).update(f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}")

        self.context = context

        # Process final evaluation results and trigger appropriate TUI styling
        error_code = context.get("ERROR_CODE", final_status) if context else final_status
        if final_status == "PASS":
            self.set_error_code(str(error_code or "PASS"), "pass")
            self.set_result_banner("PASS")
        elif final_status == "STOP":
            self.set_error_code(str(error_code or "STOP"), "running")
            self.set_result_banner("FAIL")
        elif final_status == "CHECK":
            self.set_error_code(str(error_code or "CHECK"), "check")
            self.set_result_banner("CHECK")
        else:
            error_code = str(error_code or "UNKNOWN")
            self.set_error_code(error_code, "fail")
            self.set_result_banner("FAIL")

        # Keep the final status banner visible before unlocking input for the next scan
        await asyncio.sleep(1.8)

        serial_input.value = ""
        serial_input.disabled = False
        start_button.disabled = False
        start_button.label = "Start"
        self.call_after_refresh(self.focus_serial_input)


if __name__ == "__main__":
    SapasDashboard().run()
