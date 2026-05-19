import re

import sapas
from sapas import TestItem


class GetCpuSerialNumber(TestItem):
    measure_file = "get_cpu_serial_number_measure.txt"
    result_file = "get_cpu_serial_number_result.csv"
    criteria_file = "get_cpu_serial_number_criteria.csv"
    logs_folder = "GET_CPU_SN"
    logs_name = "get_cpu_serial_number.log"

    def run_test(self):
        # 1. Retrieve the SSH connection instance from the environment.
        #    Note: 'main_dut' must match the link name defined in /Alishan/tables/project.yaml.
        #    You can change this string to anything, as long as it matches the name in your YAML.
        #
        #    CONNECTION MANAGEMENT:
        #    You DO NOT need to manually close this connection. Sapas automatically reuses 
        #    active connections across different test items and will safely clean them up 
        #    once the entire station execution is completed.
        pSSH = sapas.link.get('main_dut')

        # 2. Execute the Linux command via SSH to retrieve the CPU serial number
        output = pSSH.exec(
            "cat /proc/cpuinfo | awk '/Serial/ {print $3}'"
        )

        # 3. Parse and validate the CPU serial number format (expected to be a 16-character hex string)
        match = re.search(r"[0-9a-fA-F]{16}", output)
        if not match:
            raise Exception("Cannot find valid SoC serial number format")

        # 4. Assign the parsed value to the measure attribute. 
        #    The framework will automatically validate this against the Criteria file later.
        self.measure.CPU_SN = match.group(0)