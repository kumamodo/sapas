import re
import time
from sapas import TestItem

class GetMcuVersion(TestItem):
    measure_file = "get_mcu_version.txt"
    result_file = "get_mcu_version_result.csv"
    criteria_file = "get_mcu_version_criteria.csv"
    logs_folder = "GET_MCU_VERSION"
    logs_name = "get_mcu_version.log"

    def run_test(self):
        pUDP = self.link.get('main_mcu')
        resultMessage = ""

        # Retry up to 3 times before giving up
        for attempt in range(1, 4):
            resultMessage = pUDP.exec('revision', timeout=0.5)
            if resultMessage:
                break
            self.log(f"No response from MCU, retrying... ({attempt}/3)")
            time.sleep(1)
        else:
            self.log("MCU did not respond after 3 attempts.")
            resultMessage = "Exception"

        self.log(resultMessage)

        # Extract and log the MCU SW revision
        ver_match = re.search(r"SW Revision\s+:\s+([0-9.]+)", resultMessage)
        self.measure.MCU_SW_VERSION = ver_match.group(1) if ver_match else 'Exception'