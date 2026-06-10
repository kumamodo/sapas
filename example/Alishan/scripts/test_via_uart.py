
import sapas
from sapas import ActionItem


class TestViaUart(ActionItem):
    """
    This script attempts to connect to 'uart_device' (defined in project.yaml)
    and executes basic shell commands on the Raspberry Pi via UART.
    """

    def run_action(self):
        # 1. Get the serial connection instance. 
        # The 'uart_device' link is defined in your project.yaml.
        uart = sapas.link.get("uart_device")

        self.info("--- Starting UART Connectivity Test ---")


        # 2. Execute a simple command to check system info
        response = uart.exec("uname -a")
        sapas.info(f"Response:\n{response}")

        # 3. Check system uptime
        response = uart.exec("uptime")
        sapas.info(f"Response:\n{response}")

        # 4. Check memory usage
        response = uart.exec("free -m")
        sapas.info(f"Response:\n{response}")

        sapas.info("--- UART Test Completed ---")
