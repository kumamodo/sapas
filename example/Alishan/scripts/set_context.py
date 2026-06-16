# scripts/set_context.py
import sapas
from sapas import TestItem

class ReadMacAddress(TestItem):
    measure_file="set_context.txt"
    result_file="set_context_result.csv"
    criteria_file="set_context_criteria.csv"
    logs_folder="SET_CONTEXT"
    logs_name="set_context.log"

    def run_test(self):
        sapas.info("Reading MAC address from DUT...")
        
        # Simulated raw data obtained from hardware (e.g., via SSH/UART command).
        mock_output = "Physical Address. . . . . . . . . : 00-1A-2B-3C-4D-5E"
        
        # Parse out the MAC address.
        mac_address = mock_output.split()[-1]
        sapas.info(f"Successfully parsed MAC address: {mac_address}")
        
        # Core functionality: write variables into the global Context.
        sapas.var.set("DUT_MAC_ADDR", mac_address)
        
        # Record the measured value and mark this test item as completed.
        # The name "READ_MAC_ADDRESS" comes from the item name defined in your criteria file.

        # Method 1: Key-value pair format (supports spaces/special characters, suitable for dynamic keys).
        sapas.measure['READ MAC ADDRESS'] = mac_address
        # Method 2: Attribute-style format (more intuitive to write, but names cannot contain spaces).
        sapas.measure.READ_MAC_ADDRESS = mac_address

        # Both methods above can write values into the measure field.