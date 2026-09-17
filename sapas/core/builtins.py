import time
import math
import socket
import subprocess
import platform
from typing import Optional, Union

from sapas.modules.log import info, warn, error
from sapas.runtime.runtime import ctx


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


def _resolve_target_host(target: str) -> tuple[str, Optional[int]]:
    """
    Resolves a target string (IP, hostname, or LINK target name in config)
    to a (host_ip_or_name, optional_port) tuple.
    """
    host = target
    port = None

    try:
        # Check if target is a configured LINK target in ctx.link
        if hasattr(ctx, "link") and ctx.link is not None:
            config = getattr(ctx.link, "_config", {})
            if target in config:
                cfg = config[target]
                host = cfg.get("host") or cfg.get("network_host") or cfg.get("ip") or target
                if ":" in str(host) and not host.startswith("["):
                    parts = str(host).split(":")
                    host = parts[0]
                    port = int(parts[1])
    except Exception:
        pass

    return str(host), port


def _single_ping_execute(host: str, count: int, timeout: float, check_port: Optional[int]) -> bool:
    """Internal helper to execute a single ping attempt via TCP socket or ICMP system ping."""
    if check_port is not None:
        try:
            with socket.create_connection((host, int(check_port)), timeout=timeout):
                return True
        except (socket.timeout, OSError):
            return False

    sys_name = platform.system().lower()
    param_n = "-n" if sys_name == "windows" else "-c"
    param_w = "-w" if sys_name == "windows" else "-W"
    timeout_val = str(int(timeout * 1000)) if sys_name == "windows" else str(max(1, int(timeout)))

    cmd = ["ping", param_n, str(count), param_w, timeout_val, host]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            return False
        out_lower = res.stdout.lower()
        if "unreachable" in out_lower or "timed out" in out_lower or "100% loss" in out_lower:
            return False
        return True
    except Exception:
        return False


def ping(
    target: str,
    count: int = 1,
    timeout: float = 1.0,
    port: Optional[int] = None,
    interval: float = 1.0,
    log_output: bool = True
) -> bool:
    """
    Ping a device or host to check reachability.
    
    If timeout <= 1.0, performs a single quick status check.
    If timeout > 1.0, polls the target up to `timeout` seconds with live countdown logging.
    
    Args:
        target (str): IP address, hostname, or LINK target name (e.g., 'main_dut', '192.168.1.110').
        count (int): Number of ICMP ping requests per check (default 1).
        timeout (float): Timeout in seconds. If > 1.0, polling wait mode is enabled (default 1.0s).
        port (int, optional): If specified, tests TCP connection on this port instead of ICMP.
        interval (float): Polling interval in seconds when timeout > 1.0 (default 1.0s).
        log_output (bool): Whether to output log info (default True).
        
    Returns:
        bool: True if reachable, False otherwise.
    """
    host, resolved_port = _resolve_target_host(target)
    check_port = port if port is not None else resolved_port

    if timeout <= 1.0:
        success = _single_ping_execute(host, count, timeout, check_port)
        if log_output:
            mode_str = " (TCP)" if check_port else ""
            if success:
                info(f"[PING] {target} ({host}) is ONLINE{mode_str}", tag='PING')
            else:
                warn(f"[PING] {target} ({host}) is OFFLINE{mode_str}", tag='PING')
        return success

    # Polling mode (timeout > 1.0)
    if log_output:
        info(f"[PING] Waiting for {target} to come online [Timeout: {timeout:g}s]...", tag='PING')

    start_time = time.time()
    last_logged_sec = -1

    while True:
        elapsed = time.time() - start_time
        remaining = timeout - elapsed
        if remaining <= 0:
            break

        current_sec = int(math.ceil(remaining))
        if log_output and current_sec != last_logged_sec and current_sec >= 1:
            info(f"[PING] Waiting for {target}... ({current_sec}s remaining)", tag='PING')
            last_logged_sec = current_sec

        step_start = time.time()
        single_timeout = min(interval, 0.4)
        if _single_ping_execute(host, count, single_timeout, check_port):
            total_elapsed = time.time() - start_time
            if log_output:
                info(f"[PING] {target} is now ONLINE! (took {total_elapsed:.1f}s)", tag='PING')
            return True

        step_duration = time.time() - step_start
        sleep_needed = max(0.01, interval - step_duration)
        remaining_after_step = timeout - (time.time() - start_time)
        if remaining_after_step <= 0:
            break
        time.sleep(min(sleep_needed, remaining_after_step))

    if log_output:
        error(f"[PING] Timeout waiting for {target} to come online after {timeout:g}s", tag='PING')
    return False
