import time
import math
from sapas.modules.log import info


def sleep(seconds: float | int) -> None:
    """
    Sapas built-in delay: prints a detailed countdown in the log to keep the operator informed.
    """
    sec = float(seconds)
    info(f"[DELAY] Sleep for {sec} seconds.")

    fraction = round(sec - math.floor(sec), 4)
    if fraction > 0:
        info(f"[DELAY] Countdown {sec:g} sec...")
        time.sleep(fraction)
        remaining = float(math.floor(sec))
    else:
        remaining = sec

    while remaining >= 1.0:
        info(f"[DELAY] Countdown {int(remaining)} sec...")
        time.sleep(1.0)
        remaining -= 1.0

    info("[DELAY] Sleep finished.")
