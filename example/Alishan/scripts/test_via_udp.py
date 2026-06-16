import re
import sapas
from sapas import TestItem

class GetMcuVersion(TestItem):
    measure_file = "get_mcu_version.txt"
    result_file = "get_mcu_version_result.csv"
    criteria_file = "get_mcu_version_criteria.csv"
    logs_folder = "GET_MCU_VERSION"
    logs_name = "get_mcu_version.log"

    def run_test(self):
        pUDP = sapas.link.get('main_mcu')
        resultMessage = ""

        # Retry up to 3 times before giving up
        for attempt in range(1, 4):
            resultMessage = pUDP.exec('revision', timeout=0.5)
            if resultMessage:
                break
            sapas.info(f"No response from MCU, retrying... ({attempt}/3)")
            sapas.sleep(1)
        else:
            sapas.info("MCU did not respond after 3 attempts.")
            resultMessage = "Exception"

        sapas.info(resultMessage)

        # Extract and log the MCU SW revision
        ver_match = re.search(r"SW Revision\s+:\s+([0-9.]+)", resultMessage)
        sapas.measure.MCU_SW_VERSION = ver_match.group(1) if ver_match else 'Exception'