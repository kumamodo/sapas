# scripts/get_context.py
import sapas
from sapas import TestItem

class VerifyMacAddress(TestItem):
    measure_file="get_context.txt"
    result_file="get_context_result.csv"
    criteria_file="get_context_criteria.csv"
    logs_folder="GET_CONTEXT"
    logs_name="get_context.log"

    def run_test(self):
        # Core functionality: explicitly check prerequisite dependency variables.
        # If the previous test item was not executed, or this variable was never set,
        # the framework will automatically intercept it here and provide a clear error message.
        sapas.var.require("DUT_MAC_ADDR")
        
        # Core functionality: retrieve the global variable left by the previous test item.
        mac_addr = sapas.var.get("DUT_MAC_ADDR")
        sapas.info(f"The MAC address retrieved from the global Context is: {mac_addr}")
        
        # Execute the subsequent test logic (e.g., format validation).
        if mac_addr.startswith("00-1A"):
            sapas.info("MAC prefix validation passed!")
            self.measure['PREFIX CHECK'] = 'VALID'
        else:
            sapas.error("Invalid MAC prefix!")
            self.measure['PREFIX CHECK'] = 'INVALID'