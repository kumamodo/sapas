import time
import math
from sapas.modules.log import info


def sleep(seconds: float | int) -> None:
    """
    Sapas built-in delay: prints a detailed countdown in the log to keep the operator informed.
    """
    sec = float(seconds)
    info(f"[DELAY] Sleep for {sec} seconds.")

    remaining = sec
    # Countdown in 1-second intervals while there's at least 1 second left
    while remaining >= 1.0:
        current_display = math.ceil(remaining)
        info(f"[DELAY] Countdown {current_display} sec...")
        time.sleep(1.0)
        remaining -= 1.0

    # Handle remaining fractional time (e.g. 0.5 seconds)
    if remaining > 0:
        info(f"[DELAY] Countdown {remaining:.1f} sec...")
        time.sleep(remaining)

    info("[DELAY] Sleep finished.")
