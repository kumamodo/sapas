import sapas
from sapas import ActionItem


class TestADBConnection(ActionItem):
    """
    Example script: Test ADB dual-mode driver.
    This script attempts to connect to 'adb_device' (defined in project.yaml) and executes basic commands.
    """

    def run_action(self):
        sapas.info("Getting ADB connection instance [adb_device]...")

        # Retrieve 'adb_device' connection from link.
        # It automatically executes connection logic based on priorities defined in project.yaml.
        try:
            device = sapas.link.get('adb_device')
        except Exception as e:
            sapas.error(f"Connection failed: {e}")
            return

        sapas.info(f"Current device ID: {device.current_serial}")

        # Execute basic ADB commands
        sapas.info("Executing command: uptime")
        uptime = device.exec("uptime")
        sapas.info(f"Uptime output: {uptime.strip()}")

        sapas.info("Executing command: uname -a")
        uname = device.exec("uname -a")
        sapas.info(f"System info: {uname.strip()}")

        # Demonstrate getting Android properties (if target is an Android device)
        sapas.info("Attempting to get Android property: ro.product.model")
        model = device.exec("getprop ro.product.model")
        if model.strip():
            sapas.info(f"Device model: {model.strip()}")
        else:
            sapas.info("Could not retrieve ro.product.model. Target might not be Android or permission denied.")

        sapas.info("ADB driver test completed.")
