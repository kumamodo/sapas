import sapas
from sapas import ActionItem


@sapas.param("--target", type=str, default="main_dut", help="Target IP address, hostname, or LINK name to ping")
@sapas.param("--timeout", type=float, default=3.0, help="Ping timeout in seconds")
class PingDevice(ActionItem):
    """
    An ActionItem example demonstrating how to use sapas.ping to check network reachability
    or wait for a rebooting device to come back online in Sapas.
    """

    def run_action(self):
        target = sapas.args.target
        timeout = sapas.args.timeout

        sapas.info(f"=== Starting Network Reachability Check for [{target}] ===")

        # sapas.ping handles both instant single check (timeout <= 1.0)
        # and multi-second polling with countdown (timeout > 1.0).
        # Supports IP address (e.g. '192.168.1.110') or configured LINK name (e.g. 'main_dut')
        is_online = sapas.ping(target, timeout=timeout)

        if is_online:
            sapas.info(f"Target [{target}] is ONLINE and reachable.")
        else:
            sapas.fail(f"Target [{target}] is OFFLINE or unreachable after {timeout:g}s timeout.")
