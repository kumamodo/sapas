import sapas
from sapas import ActionItem


class TestADBConnection(ActionItem):
    """
    Example script: Test ADB dual-mode driver.
    This script attempts to connect to 'dut1' (defined in project.yaml) and executes basic commands.
    """

    def run_action(self):
        self.info("Getting ADB connection instance [dut1]...")

        # Retrieve 'dut1' connection from link.
        # It automatically executes connection logic based on priorities defined in project.yaml.
        try:
            device = sapas.link.get('dut1')
        except Exception as e:
            self.error(f"Connection failed: {e}")
            return

        self.info(f"Current device ID: {device.current_serial}")

        # Execute basic ADB commands
        self.info("Executing command: uptime")
        uptime = device.exec("uptime")
        self.info(f"Uptime output: {uptime.strip()}")

        self.info("Executing command: uname -a")
        uname = device.exec("uname -a")
        self.info(f"System info: {uname.strip()}")

        # Demonstrate getting Android properties (if target is an Android device)
        self.info("Attempting to get Android property: ro.product.model")
        model = device.exec("getprop ro.product.model")
        if model.strip():
            self.info(f"Device model: {model.strip()}")
        else:
            self.info("Could not retrieve ro.product.model. Target might not be Android or permission denied.")

        self.info("ADB driver test completed.")
