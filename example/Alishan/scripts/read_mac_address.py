# scripts/read_mac_address.py
import sapas
from sapas import TestItem

class ReadMacAddress(TestItem):
    measure_file="read_mac_adress.txt"
    result_file="read_mac_adress_result.csv"
    criteria_file="read_mac_adress_criteria.csv"
    logs_folder="READ_MAC_ADDRESS"
    logs_name="read_mac_adress.log"

    def run_test(self):
        self.log("Reading MAC address from DUT...")
        
        # Simulated raw data obtained from hardware (e.g., via SSH/UART command).
        mock_output = "Physical Address. . . . . . . . . : 00-1A-2B-3C-4D-5E"
        
        # Parse out the MAC address.
        mac_address = mock_output.split()[-1]
        self.log(f"Successfully parsed MAC address: {mac_address}")
        
        # Core functionality: write variables into the global Context.
        sapas.var.set("DUT_MAC_ADDR", mac_address)
        
        # Record the measured value and mark this test item as completed.
        # The name "READ_MAC_ADDRESS" comes from the item name defined in your criteria file.

        # Method 1: Key-value pair format (supports spaces/special characters, suitable for dynamic keys).
        self.measure['READ MAC ADDRESS'] = mac_address
        # Method 2: Attribute-style format (more intuitive to write, but names cannot contain spaces).
        self.measure.READ_MAC_ADDRESS = mac_address

        # Both methods above can write values into the measure field.