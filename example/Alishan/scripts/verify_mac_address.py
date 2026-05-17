# scripts/verify_mac_address.py
import sapas
from sapas import TestItem

class VerifyMacAddress(TestItem):
    measure_file="verify_mac_adress.txt"
    result_file="verify_mac_adress_result.csv"
    criteria_file="verify_mac_adress_criteria.csv"
    logs_folder="VERIFY_MAC_ADDRESS"
    logs_name="verify_mac_adress.log"

    def run_test(self):
        # Core functionality: explicitly check prerequisite dependency variables.
        # If the previous test item was not executed, or this variable was never set,
        # the framework will automatically intercept it here and provide a clear error message.
        sapas.var.require("DUT_MAC_ADDR")
        
        # Core functionality: retrieve the global variable left by the previous test item.
        mac_addr = sapas.var.get("DUT_MAC_ADDR")
        self.log(f"The MAC address retrieved from the global Context is: {mac_addr}")
        
        # Execute the subsequent test logic (e.g., format validation).
        if mac_addr.startswith("00-1A"):
            self.log("MAC prefix validation passed!")
            self.measure['PREFIX CHECK'] = 'VALID'
        else:
            self.log("Invalid MAC prefix!")
            self.measure['PREFIX CHECK'] = 'INVALID'