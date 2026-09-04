import asyncio
import contextlib
import logging
import threading
from sapas.cli import setup_context
from sapas.core.runner import Runner


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


def execute_real_flow(
    args,
    context,
    serial_number: str,
    timestamp: str,
    emit_line_cb,
    stop_requested: bool = False,
    abort_requested_cb=None,
    on_context_created=None,
):
    """Spins up synchronous flow execution engines with structured console logging redirection wrappers."""
    if abort_requested_cb and abort_requested_cb():
        return "STOP", context

    args.serialNumber = serial_number
    args.timeStamp = timestamp

    run_context = setup_context(args)
    if on_context_created:
        on_context_created(run_context)
    if stop_requested:
        run_context.set("STOP_REQUESTED", True)
    runner = Runner(run_context)

    tui_handler = TUILogHandler(lambda line: emit_line_cb(line, ""))
    tui_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(tui_handler)

    stderr_capture = LineCapture(lambda line: emit_line_cb(line, "bold red"), "STDERR")
    try:
        with contextlib.redirect_stderr(stderr_capture):
            runner.execute_flows(args)
    finally:
        stderr_capture.flush()
        root_logger.removeHandler(tui_handler)

    return run_context.get("ERROR_CODE", "UNKNOWN"), run_context


async def run_flow_in_daemon_thread(
    args,
    context,
    serial_number: str,
    timestamp: str,
    emit_line_cb,
    stop_requested: bool = False,
    abort_requested_cb=None,
    call_from_thread_fn=None,
    on_context_created=None,
):
    """Run the blocking runner without tying UI shutdown to asyncio's default executor."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def finish(result=None, error: BaseException | None = None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(result)

    def worker() -> None:
        try:
            result = execute_real_flow(
                args,
                context,
                serial_number,
                timestamp,
                emit_line_cb=emit_line_cb,
                stop_requested=stop_requested,
                abort_requested_cb=abort_requested_cb,
                on_context_created=lambda ctx: call_from_thread_fn(on_context_created, ctx) if on_context_created else None,
            )
        except BaseException as exc:
            if not (abort_requested_cb and abort_requested_cb()):
                with contextlib.suppress(Exception):
                    call_from_thread_fn(finish, None, exc)
        else:
            if not (abort_requested_cb and abort_requested_cb()):
                with contextlib.suppress(Exception):
                    call_from_thread_fn(finish, result, None)

    thread = threading.Thread(target=worker, name="SapasRunnerThread", daemon=True)
    thread.start()
    return await future


def execute_single_step_debug(
    context,
    cli_args,
    step,
    emit_line_cb,
) -> int:
    """Synchronously executes a single test step in TE debug mode with isolated outputs."""
    from datetime import datetime
    from sapas.modules.message import Message

    serial_number = getattr(cli_args, "serialNumber", "sapas999999999") or "sapas999999999"

    runner = Runner(context)
    runner.serialNumber = serial_number
    # Isolate all step logs and results to output/<serialNumber>/debug
    runner.timeStamp = "debug"
    runner.critical_error = False
    runner.stop_test_file_path = runner.workspace_root / "output" / runner.serialNumber / "stop.test"

    # Write debug runner logs to output/<serialNumber>/debug/debug.log
    debug_dir = runner.workspace_root / "output" / runner.serialNumber / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_log_path = debug_dir / "debug.log"

    msg_wrapper = Message(str(debug_log_path), "RUNNER_DEBUG")
    runner.logger = msg_wrapper.logger

    # Preserve and restore original RUNNER_LOGGER in context
    original_runner_logger = context.get("RUNNER_LOGGER") if context else None
    if context:
        context.set("RUNNER_LOGGER", runner.logger)

    tui_handler = TUILogHandler(lambda line: emit_line_cb(line, ""))
    tui_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(tui_handler)

    stderr_capture = LineCapture(lambda line: emit_line_cb(line, "bold red"), "STDERR")
    return_code = -1
    try:
        with contextlib.redirect_stderr(stderr_capture):
            command = (step.command or "").strip().lower()
            if command == "delay":
                runner._cmd_delay(step.flow_item)
                return_code = 0
            elif command == "prompt":
                runner._cmd_prompt(step.flow_item)
                return_code = 0
            else:
                return_code = runner._run_test_script(step.flow_item)
    except Exception as e:
        emit_line_cb(f"[ERROR] Exception during debug re-test: {e}", "bold red")
        return_code = -1
    finally:
        stderr_capture.flush()
        root_logger.removeHandler(tui_handler)
        if context and original_runner_logger is not None:
            context.set("RUNNER_LOGGER", original_runner_logger)
        # Explicitly close file handlers to release Windows file locks
        msg_wrapper.close()

    return return_code


async def run_single_step_in_daemon_thread(
    context,
    cli_args,
    step,
    emit_line_cb,
    call_from_thread_fn=None,
) -> int:
    """Runs a single test step in a daemon thread without blocking the TUI loop."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def finish(result=None, error: BaseException | None = None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(result)

    def worker() -> None:
        try:
            rc = execute_single_step_debug(
                context=context,
                cli_args=cli_args,
                step=step,
                emit_line_cb=emit_line_cb,
            )
        except BaseException as exc:
            with contextlib.suppress(Exception):
                call_from_thread_fn(finish, None, exc)
        else:
            with contextlib.suppress(Exception):
                call_from_thread_fn(finish, rc, None)

    thread = threading.Thread(target=worker, name="SapasDebugStepThread", daemon=True)
    thread.start()
    return await future

