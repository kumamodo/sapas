"""Background daemon loop for Sapas Station Guard."""
import os
import sys
import time
import signal
from sapas.guard.constants import GUARD_PID_FILE
from sapas.guard.lock_manager import get_lock_data, release_lock, is_pid_alive
from sapas.guard.ui import StationGuardWindow


class StationGuardDaemon:
    """Monitors .station_lock state and controls fullscreen alert displays."""

    def __init__(self) -> None:
        self.window = StationGuardWindow()
        self.running = True

    def _write_pid(self) -> None:
        try:
            GUARD_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            GUARD_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass

    def _cleanup_pid(self) -> None:
        try:
            if GUARD_PID_FILE.exists():
                GUARD_PID_FILE.unlink()
        except Exception:
            pass

    def stop(self) -> None:
        """Stops the daemon loop."""
        self.running = False
        self.window.close()
        self._cleanup_pid()

    def run(self) -> None:
        """Main monitoring loop."""
        self._write_pid()

        def _handle_signal(signum, frame):
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except Exception:
            pass

        try:
            while self.running:
                lock_data = get_lock_data()

                if lock_data:
                    if not self.window.is_visible():
                        self.window.show(lock_data)
                    else:
                        self.window.update_data(lock_data)
                else:
                    if self.window.is_visible():
                        self.window.close()

                # Process UI events if visible, otherwise sleep quietly
                if self.window.is_visible():
                    try:
                        self.window.root.update()
                    except Exception:
                        self.window.close()
                    time.sleep(0.1)
                else:
                    time.sleep(0.5)

        finally:
            self.stop()


def main() -> None:
    """Entry point for pythonw -m sapas.guard.daemon."""
    daemon = StationGuardDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
