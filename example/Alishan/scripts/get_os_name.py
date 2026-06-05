import subprocess
import sapas
from sapas import TestItem


class OsName(TestItem):
    measure_file="get_os_name.txt"
    result_file="get_os_name_result.csv"
    criteria_file="get_os_name_criteria.csv"
    logs_folder="GET_OS_NAME"
    logs_name="get_os_name.log"

    def run_test(self):
        # Execute the command and strip leading and trailing newline characters.
        raw_output = subprocess.check_output('ver', shell=True).decode(errors='ignore').strip()
        sapas.info(f"Raw System Output: {raw_output}")

        # Split the string into a list of tokens, and filter out empty strings
        output_segments = [segment for segment in raw_output.split(' ') if segment]
        
        # Extract the key information (e.g., Windows).
        # Logic: take the second element from the list.
        if len(output_segments) >= 2:
            extracted_name = output_segments[1]
        else:
            extracted_name = "Unknown"

        # Write the measured value.
        # The name "OS_NAME" comes from the item name defined in your criteria file.
        self.measure.OS_NAME = extracted_name
        sapas.info(f"Extracted OS Name for Measurement: {extracted_name}")