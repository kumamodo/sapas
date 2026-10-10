"""Tkinter fullscreen alert window for Station Guard."""
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

try:
    import winsound
except ImportError:
    winsound = None


class StationGuardWindow:
    """Fullscreen top-level alert screen blocking local desktop during remote maintenance."""

    def __init__(self) -> None:
        self.root: tk.Tk | None = None
        self._lbl_message: tk.Label | None = None
        self._lbl_ip: tk.Label | None = None
        self._lbl_time: tk.Label | None = None
        self._beep_job: str | None = None
        self._beep_count: int = 0
        self._key_history: list[str] = []
        self._current_data: dict = {}

    def is_visible(self) -> bool:
        """Returns True if the fullscreen window is currently displayed."""
        return self.root is not None

    def show(self, data: dict) -> None:
        """Constructs and displays the fullscreen topmost warning window."""
        if self.root is not None:
            self.update_data(data)
            return

        self._current_data = data
        self._key_history.clear()
        self.root = tk.Tk()
        self.root.title("Sapas Station Guard - Remote Maintenance Warning")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#990000")

        # Disable Alt+F4 / Window Close
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        # On-site supervisor emergency override unlock (Supervisor Sequence: Up Up Down Down Left Right Left Right B A B A)
        self.root.bind("<Key>", self._handle_key)

        # Grab and continuously hold keyboard focus to prevent input leaking to background windows
        self.root.bind("<FocusOut>", lambda event: self._reclaim_focus())
        self.root.bind("<Button-1>", lambda event: self._reclaim_focus())

        # Main Layout Container
        container = tk.Frame(self.root, bg="#990000")
        container.pack(expand=True, fill="both", padx=40, pady=30)

        # Center Container - Automatically anchors all primary elements to the exact screen center
        center_box = tk.Frame(container, bg="#990000")
        center_box.pack(expand=True)

        # 1. Colossal Hazard Triangle (120pt - dominant warning beacon)
        lbl_icon = tk.Label(
            center_box,
            text="⚠️",
            font=("Segoe UI Emoji", 120),
            fg="#FFE600",
            bg="#990000",
        )
        lbl_icon.pack(pady=(0, 25))

        # 2. Main Title (36pt bold white)
        lbl_title = tk.Label(
            center_box,
            text="REMOTE DEBUG IN PROGRESS",
            font=("Segoe UI", 36, "bold"),
            fg="#FFFFFF",
            bg="#990000",
            justify="center",
        )
        lbl_title.pack(pady=(0, 10))

        # 3. Warning Subtitle (32pt bold hazard yellow - with generous breathing room before card)
        lbl_sub = tk.Label(
            center_box,
            text="DO NOT TOUCH FIXTURE OR LOAD DUT",
            font=("Segoe UI", 32, "bold"),
            fg="#FFE600",
            bg="#990000",
            justify="center",
        )
        lbl_sub.pack(pady=(0, 55))

        # 4. Details Panel - 3-column Grid layout ensuring 100% pixel-perfect colon alignment
        card = tk.Frame(
            center_box,
            bg="#111111",
            highlightbackground="#FFE600",
            highlightcolor="#FFE600",
            highlightthickness=2,
            padx=70,
            pady=30,
        )
        card.pack(pady=(0, 10))

        # Row 0: REASON
        lbl_k_reason = tk.Label(
            card,
            text="REASON",
            font=("Segoe UI", 18, "bold"),
            fg="#FFFFFF",
            bg="#111111",
            anchor="w",
        )
        lbl_k_reason.grid(row=0, column=0, sticky="w", pady=8)

        lbl_c_reason = tk.Label(
            card,
            text=":",
            font=("Segoe UI", 18, "bold"),
            fg="#FFFFFF",
            bg="#111111",
        )
        lbl_c_reason.grid(row=0, column=1, sticky="w", padx=(10, 15), pady=8)

        self._lbl_message = tk.Label(
            card,
            text=data.get("message", "Remote maintenance"),
            font=("Segoe UI", 18, "bold"),
            fg="#FFFFFF",
            bg="#111111",
            anchor="w",
        )
        self._lbl_message.grid(row=0, column=2, sticky="w", pady=8)

        # Row 1: CLIENT IP
        lbl_k_ip = tk.Label(
            card,
            text="CLIENT IP",
            font=("Segoe UI", 18, "bold"),
            fg="#4FC3F7",
            bg="#111111",
            anchor="w",
        )
        lbl_k_ip.grid(row=1, column=0, sticky="w", pady=8)

        lbl_c_ip = tk.Label(
            card,
            text=":",
            font=("Segoe UI", 18, "bold"),
            fg="#4FC3F7",
            bg="#111111",
        )
        lbl_c_ip.grid(row=1, column=1, sticky="w", padx=(10, 15), pady=8)

        self._lbl_ip = tk.Label(
            card,
            text=data.get("ip", "Localhost"),
            font=("Segoe UI", 18, "bold"),
            fg="#4FC3F7",
            bg="#111111",
            anchor="w",
        )
        self._lbl_ip.grid(row=1, column=2, sticky="w", pady=8)

        # Row 2: LOCK TIME
        lbl_k_time = tk.Label(
            card,
            text="LOCK TIME",
            font=("Segoe UI", 18, "bold"),
            fg="#B0BEC5",
            bg="#111111",
            anchor="w",
        )
        lbl_k_time.grid(row=2, column=0, sticky="w", pady=8)

        lbl_c_time = tk.Label(
            card,
            text=":",
            font=("Segoe UI", 18, "bold"),
            fg="#B0BEC5",
            bg="#111111",
        )
        lbl_c_time.grid(row=2, column=1, sticky="w", padx=(10, 15), pady=8)

        self._lbl_time = tk.Label(
            card,
            text=data.get("time", ""),
            font=("Segoe UI", 18, "bold"),
            fg="#B0BEC5",
            bg="#111111",
            anchor="w",
        )
        self._lbl_time.grid(row=2, column=2, sticky="w", pady=8)

        # 5. Footer Notice
        lbl_footer = tk.Label(
            container,
            text="[ This alert will automatically close once remote maintenance is unlocked ]",
            font=("Segoe UI", 13),
            fg="#FFCDD2",
            bg="#990000",
            justify="center",
        )
        lbl_footer.pack(side="bottom", pady=20)

        self._start_beep_loop()
        self.force_foreground_focus()
        self.root.update()

    def force_foreground_focus(self) -> None:
        """Forces the Windows OS to bring this alert window to the active foreground and give it keyboard focus."""
        if not self.root:
            return
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                fg_hwnd = user32.GetForegroundWindow()

                if fg_hwnd != hwnd:
                    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
                    cur_thread = kernel32.GetCurrentThreadId()

                    if fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, True)

                    # Bring window to top and set foreground
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.SetFocus(hwnd)

                    if fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, False)
            except Exception:
                pass

    def _reclaim_focus(self) -> None:
        """Reclaims keyboard focus if lost to any background window."""
        if self.root:
            try:
                self.root.after_idle(self.force_foreground_focus)
            except Exception:
                pass

    def update_data(self, data: dict) -> None:
        """Updates text fields if lock data has changed while window is open."""
        if not self.root:
            return
        if data != self._current_data:
            self._current_data = data
            if self._lbl_message:
                self._lbl_message.config(text=data.get("message", "Remote maintenance"))
            if self._lbl_ip:
                self._lbl_ip.config(text=data.get("ip", "Localhost"))
            if self._lbl_time:
                self._lbl_time.config(text=data.get("time", ""))
        self.root.update()

    def _play_beep_async(self, duration_ms: int = 1000) -> None:
        """Plays a warning beep asynchronously on Windows."""
        if winsound and sys.platform == "win32":
            def _beep():
                try:
                    winsound.Beep(1000, duration_ms)
                except Exception:
                    pass
            threading.Thread(target=_beep, daemon=True).start()

    def _start_beep_loop(self) -> None:
        """Starts alert beeping: ~1s long beep, pause ~0.4s, repeating 5 times."""
        self._stop_beep_loop()
        self._beep_count = 0
        self._beep_tick()

    def _beep_tick(self) -> None:
        """Executes a ~1-second beep up to 5 times (with ~0.4s pause between beeps)."""
        if not self.root:
            return
        if self._beep_count < 5:
            self._play_beep_async(1000)
            self._beep_count += 1
            if self._beep_count < 5:
                # 1000ms duration + 400ms pause = 1400ms total cadence
                self._beep_job = self.root.after(1400, self._beep_tick)

    def _stop_beep_loop(self) -> None:
        """Cancels any pending beep timer."""
        if self.root and self._beep_job:
            try:
                self.root.after_cancel(self._beep_job)
            except Exception:
                pass
        self._beep_job = None

    def close(self) -> None:
        """Destroys and hides the warning window, restoring the regular desktop."""
        self._stop_beep_loop()
        self._beep_count = 0
        self._key_history.clear()
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None
            self._lbl_message = None
            self._lbl_ip = None
            self._lbl_time = None
            self._current_data = {}

    def _handle_key(self, event) -> None:
        """Listens for on-site supervisor unlock code (Supervisor Sequence: Up Up Down Down Left Right Left Right B A B A).
        Must be completed within a rolling 10-second time window.
        """
        import time

        key = event.keysym
        now = time.monotonic()

        if key in ("Up", "Down", "Left", "Right"):
            self._key_history.append((key, now))
        elif key.lower() in ("b", "a"):
            self._key_history.append((key.lower(), now))
        else:
            self._key_history.clear()
            return

        if len(self._key_history) > 20:
            self._key_history = self._key_history[-20:]

        override_sequence = ["Up", "Up", "Down", "Down", "Left", "Right", "Left", "Right", "b", "a", "b", "a"]
        k_len = len(override_sequence)

        if len(self._key_history) >= k_len:
            sub = self._key_history[-k_len:]
            keys = [k for k, _ in sub]
            if keys == override_sequence:
                start_time = sub[0][1]
                end_time = sub[-1][1]
                if (end_time - start_time) <= 10.0:
                    self._on_site_override_unlock()
                else:
                    # Exceeded 10 seconds timeout: clear history to require a fresh input
                    self._key_history.clear()

    def _on_site_override_unlock(self) -> None:
        """Executes on-site supervisor emergency override unlock."""
        self._key_history.clear()
        from sapas.guard.lock_manager import record_override_event
        record_override_event("On-site Supervisor Key Sequence Override")
        self.close()

