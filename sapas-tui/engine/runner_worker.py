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

    tui_handler = TUILogHandler(lambda line: emit_line_cb(line, "white"))
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
