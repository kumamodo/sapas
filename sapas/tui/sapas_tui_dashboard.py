# from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import sys
import threading
import yaml
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.events import Resize
from textual.widgets import Button, Input, RichLog, Static, Footer, Header

# Ensure the repository root is in the system path for seamless module imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sapas.cli import setup_context
from sapas.core.flow_loader import FlowLoader
from sapas.core.runner import Runner

# Global Unicode Status Symbols matching standard visual weights
PASS_SYMBOL = "\u2713"
FAIL_SYMBOL = "\u274c"

# Structural flow control markers that do not map to physical execution steps
SKIP_FLOW_COMMANDS = {"cycle", "if", "end_if"}


@dataclass(frozen=True)
class TestStep:
    """Data representation of an executable test sequence item parsed from flow files."""
    item_id: str
    item_label: str
    flow_item: str
    command: str


def format_status(status: str) -> Text:
    """Generates padded Rich Text tokens for side-panel menu item statuses."""
    cells = {
        "PENDING": ("  PENDING ", "dim"),
        "RUNNING": ("  RUNNING ", "bold yellow"),
        "PASS": (f"{PASS_SYMBOL} PASS   ", "bold green"),
        "FAIL": (f"{FAIL_SYMBOL} FAIL  ", "bold red"),
        "SKIP": ("  - SKIP  ", "cyan"),
    }
    value, style = cells[status]
    return Text(value, style=style, no_wrap=True)


def plain_status(status: str) -> tuple[str, str]:
    """Retrieves the raw text and rich style pair for inline list rendering."""
    cells = {
        "PENDING": ("PENDING", "dim"),
        "RUNNING": ("RUNNING", "bold yellow"),
        "PASS": (f"{PASS_SYMBOL} PASS", "bold green"),
        "FAIL": (f"{FAIL_SYMBOL} FAIL", "bold red"),
        "SKIP": ("- SKIP", "cyan"),
    }
    return cells[status]


class TUILogHandler(logging.Handler):
    """Custom logging handler routing structured logs from root engine to TUI logging widget."""
    def __init__(self, emit_line) -> None:
        super().__init__(level=logging.INFO)
        self.emit_line = emit_line

    def emit(self, record: logging.LogRecord) -> None:
        self.emit_line(self.format(record))


class LineCapture:
    """Thread-safe stream interceptor caching standard error text chunks into structured lines."""
    def __init__(self, emit_line, stream_name: str) -> None:
        self.emit_line = emit_line
        self.stream_name = stream_name
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, data: str) -> int:
        with self._lock:
            self._buffer += data
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self.emit_line(f"[{self.stream_name}] {line.rstrip()}")
        return len(data)

    def flush(self) -> None:
        with self._lock:
            if self._buffer.strip():
                self.emit_line(f"[{self.stream_name}] {self._buffer.rstrip()}")
            self._buffer = ""


class SapasDashboard(App[None]):
    """Factory-grade Sapas production test dashboard built with Textual."""

    AUTO_FOCUS = "#serial-input"
    CSS_PATH = "dashboard.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("F2", "focus_serial", "Serial Number"),
    ]

    def __init__(self, context=None, cli_args=None) -> None:
        super().__init__()
        self.args = cli_args or Namespace(project=None, station=None, test_flow=None, serialNumber="", timeStamp="")
        self.context = context
        self.test_steps: list[TestStep] = []
        self.step_index_by_item: dict[str, str] = {}
        self.step_status: dict[str, str] = {}
        self.running_step_key: str | None = None
        self.started_at: datetime | None = None
        self.is_testing = False

    def compose(self) -> ComposeResult:
        """Constructs the TUI visual tree hierarchy layout."""
        info_box = Container(
            Static("Loading...", id="info-value", classes="box-value"), 
            classes="top-box", 
            id="info-box"
        )
        error_box = Container(
            Static("", id="error-code", classes="box-value"), 
            classes="top-box", 
            id="error-box"
        )
        elapsed_box = Container(
            Static("00:00:00.00", id="elapsed-time", classes="box-value"), 
            classes="top-box", 
            id="elapsed-box"
        )
        serial_box = Container(
            Input(placeholder="sapas1234567890", id="serial-input"),
            Button("Start", id="start-button"),
            classes="top-box",
            id="serial-box"
        )

        # Apply structural titles to standard component borders
        info_box.border_title = "Information"
        error_box.border_title = "Error Code"
        elapsed_box.border_title = "Elapsed Time"
        serial_box.border_title = "Serial Number"

        yield Container(
            Header(show_clock=True),
            Container(
                info_box,
                error_box,
                elapsed_box,
                serial_box,
                id="top-row",
            ),
            Container(
                Container(
                    Static("Items                 Status", id="items-menu-bar"),
                    Static("", id="items-list"),
                    id="items-panel"
                ),
                Container(
                    Static("Live Log", id="log-title"),
                    Static("", id="result-banner"),
                    RichLog(id="live-log", wrap=True, auto_scroll=True, highlight=False),
                    id="log-panel"
                ),
                id="main-body",
            ),
            Footer(),
            id="app-root",
        )

    async def on_mount(self) -> None:
        """Triggers asynchronous setup routines once screen mounting finishes initialization."""
        self.title = "Sapas TUI Tester"
        self.setup_dashboard_flow()       
        self.reset_station_view(clear_log=True)
        self.set_interval(0.2, self.update_elapsed)
        self.apply_responsive_layout(self.screen.size.width)
        self.query_one("#live-log", RichLog).can_focus = False
        self.call_after_refresh(self.focus_serial_input)

    def setup_dashboard_flow(self) -> None:
        """Parses operational context and resolves exact execution metadata for display fields."""
        if self.context is None:
            return

        # 1. Extract context strings
        station_name = self.context.get("STATION_NAME", "Unknown")
        project_name = self.context.get("PROJECT_NAME", "Unknown")
        workspace_root = Path(self.context.get("WORKSPACE_ROOT", Path.cwd()))
        
        # 2. Parse version.ver configuration file dynamically
        ver_path = workspace_root / project_name / "configs" / "version.yaml"
        script_version = "v0.0.0"
        try:
            with open(ver_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                script_version = data.get("version", "v0.0.0")
        except Exception as e:
            pass

        # 3. Calculate target test flow layout descriptor
        requested_flow = self.args.test_flow or f"{station_name}.flow"

        # 4. Construct metadata text string using left-aligned factory guidelines
        info_text = (
            f"Station: {station_name}\n"
            f"Script:  {script_version}\n"
            f"Flow:    {requested_flow}"
        )
        self.query_one("#info-value", Static).update(info_text)

        # 5. Extract and map executable step identifiers
        self.test_steps = self.load_station_steps()
        self.step_index_by_item = {}
        for step in self.test_steps:
            self.step_index_by_item[step.flow_item] = step.item_id
            if step.command == "delay":
                with contextlib.suppress(ValueError):
                    self.step_index_by_item[str(float(step.flow_item))] = step.item_id

    def load_station_steps(self) -> list[TestStep]:
        """Loads and filters valid steps from target flow configurations via FlowLoader."""
        if self.context is None:
            return []

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

        _, flow_items, _ = FlowLoader().load_flow(str(flow_path))
        steps: list[TestStep] = []
        for command, item in flow_items:
            command = command.strip().lower()
            item = item.strip()
            if command in SKIP_FLOW_COMMANDS:
                continue
            item_id = f"{len(steps) + 1:02d}"
            label = f"{command} {item}".strip() if command == "delay" else item
            steps.append(TestStep(item_id=item_id, item_label=label, flow_item=item, command=command))
        return steps

    def on_resize(self, event: Resize) -> None:
        """Handles screen resizing callbacks dynamically."""
        self.apply_responsive_layout(event.size.width)

    def apply_responsive_layout(self, width: int) -> None:
        """Injects responsive layout classes into screen objects based on cell width metrics."""
        self.screen.set_class(width < 100, "narrow")

    def action_focus_serial(self) -> None:
        """Action handler to focus on the serial number input field."""
        self.focus_serial_input()

    def focus_serial_input(self) -> None:
        """Sets cursor focus directly onto the primary interactive text entry component."""
        serial_input = self.query_one("#serial-input", Input)
        if not serial_input.disabled:
            serial_input.focus()

    def reset_station_view(self, *, clear_log: bool) -> None:
        """Wipes terminal panels to bring the view back to a clean standby state."""
        self.started_at = None
        self.running_step_key = None
        self.step_status = {step.item_id: "PENDING" for step in self.test_steps}
        self.render_items_list()

        if clear_log:
            self.query_one("#live-log", RichLog).clear()
            self.write_log("Station ready. Awaiting Serial Number input.", "dim")

        self.query_one("#error-code", Static).remove_class("fail", "running", "pass")
        self.query_one("#error-code", Static).update("")
        self.query_one("#elapsed-time", Static).update("00:00:00.00")
        self.set_result_banner("")

    def set_error_code(self, value: str, state: str = "") -> None:
        """Updates display contents and shifts background styles on the error status indicator."""
        error_widget = self.query_one("#error-code", Static)
        error_widget.remove_class("fail", "running", "pass")
        if state:
            error_widget.add_class(state)
        error_widget.update(value)

    def render_items_list(self) -> None:
        """Renders out clean alphanumeric step identifiers within the diagnostic item view panel."""
        item_width = 22
        text = Text()
        for step in self.test_steps:
            label = f"[{step.item_id}] {step.item_label}"
            if len(label) > item_width:
                label = label[: item_width - 1] + "."
            status, style = plain_status(self.step_status.get(step.item_id, "PENDING"))
            text.append(label.ljust(item_width), style="white")
            text.append(f" {status}\n", style=style)
        self.query_one("#items-list", Static).update(text)

    def set_step_status(self, row_key: str, status: str) -> None:
        """Updates internal dictionary keys and triggers state re-renders for test list cells."""
        self.step_status[row_key] = status
        self.render_items_list()

    def update_elapsed(self) -> None:
        """Periodic clock callback displaying accurate test execution time deltas."""
        if self.started_at is None or not self.is_testing:
            return
        elapsed = (datetime.now() - self.started_at).total_seconds()
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.query_one("#elapsed-time", Static).update(f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}")

    def write_log(self, message: str, style: str = "white") -> None:
        """Applies advanced regular expression highlight parsing to live engine output lines."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = Text(message, style=style)
        
        # Color core subsystem markers distinctly
        log_text.highlight_regex(r"\[\s*RUNNER\s*\]", "bold cyan")       
        log_text.highlight_regex(r"\[\s*ACTION\s*\]", "bold dark_orange") 
        log_text.highlight_regex(r"\[\s*USER\s*\]", "bold green")        
        log_text.highlight_regex(r"\[\s*OUT\s*\]|\[\s*ITEM\s*\]", "dim") 
        
        # Identify specific low-level data telemetry dumps
        if message.startswith("##"):
            log_text.style = "yellow"
            
        # Parse acceptance or rejection strings to match color flags
        if "PASS" in message or "accepted" in message:
            log_text.highlight_regex(r"PASS|Unit accepted\.", "bold green")
        if "FAIL" in message or "Error" in message or "rejected" in message:
            log_text.highlight_regex(r"FAIL|Error[^|]*|Unit rejected\.", "bold red")

        self.query_one("#live-log", RichLog).write(
            Text.assemble((timestamp, "dim"), (" | ", "dim"), log_text)
        )

    def write_terminal_log(self, message: str, style: str = "white") -> None:
        """Writes message logs and updates item metrics simultaneously."""
        self.update_step_state_from_log(message)
        self.write_log(message, style)

    def emit_from_worker(self, message: str, style: str = "white") -> None:
        """Safely passes incoming background worker thread messages into the TUI main loop thread."""
        self.call_from_thread(self.write_terminal_log, message, style)

    def update_step_state_from_log(self, message: str) -> None:
        """State Machine Parser: Updates current step execution records using real-time log signatures."""
        # Match standard test item start signatures
        start_match = re.search(r"sapas\s+(.+)$", message)
        if start_match:
            item = start_match.group(1).strip()
            row_key = self.step_index_by_item.get(item)
            if row_key:
                self.running_step_key = row_key
                self.set_step_status(row_key, "RUNNING")
            return

        # Match structural dynamic delay triggers
        delay_match = re.search(r"Start delay:\s+(.+?)\s+seconds", message)
        if delay_match:
            delay_item = delay_match.group(1).strip()
            row_key = self.step_index_by_item.get(delay_item)
            if row_key:
                self.running_step_key = row_key
                self.set_step_status(row_key, "RUNNING")
            return

        # Match termination tracking outputs
        result_match = re.search(r"\[Item\]:\s+(.+?)\s+\|\s+code=([-\d]+)", message)
        if result_match:
            item = result_match.group(1).strip()
            return_code = int(result_match.group(2))
            row_key = self.step_index_by_item.get(item)
            if row_key:
                self.set_step_status(row_key, "PASS" if return_code == 0 else "FAIL")
            return

        # Catch delay end confirmations
        if "Delay finished." in message and self.running_step_key:
            self.set_step_status(self.running_step_key, "PASS")
            self.running_step_key = None
            return

        # Intercept condition failures for conditionally skipped block sequences
        if "Skipping block..." in message:
            for step in self.test_steps:
                if self.step_status.get(step.item_id) == "PENDING":
                    self.set_step_status(step.item_id, "SKIP")
                    break 
            return

    def execute_real_flow(self, serial_number: str, timestamp: str):
        """Spins up synchronous flow execution engines with structured console logging redirection wrappers."""
        self.args.serialNumber = serial_number
        self.args.timeStamp = timestamp

        context = setup_context(self.args)
        runner = Runner(context)

        tui_handler = TUILogHandler(lambda line: self.emit_from_worker(line, "white"))
        tui_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(tui_handler)

        stderr_capture = LineCapture(lambda line: self.emit_from_worker(line, "bold red"), "STDERR")
        try:
            with contextlib.redirect_stderr(stderr_capture):
                runner.execute_flows(self.args)
        finally:
            stderr_capture.flush()
            root_logger.removeHandler(tui_handler)

        return context.get("ERROR_CODE", "UNKNOWN"), context

    def set_result_banner(self, result: str) -> None:
        """Toggles layout classes and maps visibility flags for overlay pass/fail result banners."""
        banner = self.query_one("#result-banner", Static)
        banner.remove_class("active", "pass", "fail")
        if not result:
            box = banner
            box.update("")
            return
        banner.add_class("active")
        banner.add_class("pass" if result == "PASS" else "fail")
        banner.update(self.make_result_banner(result))

    @staticmethod
    def make_result_banner(result: str) -> str:
        """Formats the textual payload string displayed inside overlay banners."""
        if result == "PASS":
            return "PASS    " + f"{PASS_SYMBOL} UNIT ACCEPTED"
        return "FAIL    " + f"{FAIL_SYMBOL} UNIT REJECTED"

    @on(Input.Submitted, "#serial-input")
    async def on_serial_submitted(self, event: Input.Submitted) -> None:
        """Listens for enter key submissions inside input boxes."""
        await self.start_cycle(event.value.strip())

    @on(Button.Pressed, "#start-button")
    async def on_start_pressed(self) -> None:
        """Listens for active clicks targeting the primary cycle action button."""
        await self.start_cycle(self.query_one("#serial-input", Input).value.strip())

    async def start_cycle(self, serial_number: str) -> None:
        """Validates current state constraints before spawning execution cycles."""
        if self.is_testing or not serial_number:
            self.focus_serial_input()
            return
        await self.run_station_cycle(serial_number)

    async def run_station_cycle(self, serial_number: str) -> None:
        """Core Orchestrator Loop: Executes a full automated production-line cycle flow safely."""
        self.is_testing = True
        serial_input = self.query_one("#serial-input", Input)
        start_button = self.query_one("#start-button", Button)
        serial_input.disabled = True
        start_button.disabled = True

        self.reset_station_view(clear_log=True)
        serial_input.value = serial_number
        self.started_at = datetime.now()
        self.set_error_code("RUNNING", "running")
        self.write_terminal_log(f"Serial Number accepted: {serial_number}", "bold white")
        self.write_terminal_log("Station interlock engaged. Real Sapas flow started.", "yellow")

        # Offload synchronous execution logic seamlessly to threadpools
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_status, context = await asyncio.to_thread(self.execute_real_flow, serial_number, timestamp)

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
            self.write_terminal_log("Final Result=PASS. Unit accepted.", "green")
            self.set_result_banner("PASS")
        else:
            error_code = str(error_code or "UNKNOWN")
            self.set_error_code(error_code, "fail")
            self.write_terminal_log(f"Final Result=FAIL. Error Code={error_code}. Unit rejected.", "bold red")
            self.set_result_banner("FAIL")

        # Keep the final status banner visible before unlocking input for the next scan
        await asyncio.sleep(1.8)

        serial_input.value = ""
        serial_input.disabled = False
        start_button.disabled = False
        self.call_after_refresh(self.focus_serial_input)


if __name__ == "__main__":
    SapasDashboard().run()