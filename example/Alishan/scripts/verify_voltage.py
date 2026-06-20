import time
import sapas
from sapas import TestItem


class VerifyVoltage(TestItem):
    measure_file = "verify_voltage_{}.txt"
    result_file = "verify_voltage_result_{}.csv"
    criteria_file = "verify_voltage_criteria.csv"
    logs_folder = "VERIFY_VOLTAGE_{}"
    logs_name = "verify_voltage_{}.log"

    def run_test(self):
        # Simulate reading a voltage value.
        # Here we dynamically read the tag to simulate different values for FIRST vs SECOND.
        measured_voltage = 5.05 if self.sapas_tag == "FIRST" else 12.12
        sapas.info(f"[{self.sapas_tag}] Measured Voltage: {measured_voltage}V")

        # Set the measurement value.
        # The key name "VOLTAGE" is defined as "VOLTAGE_{}" in verify_voltage_criteria.csv.
        # Sapas automatically maps it to "VOLTAGE_FIRST" or "VOLTAGE_SECOND".
        sapas.measure.VOLTAGE = measured_voltage
        sapas.info(f"[{self.sapas_tag}] Saved VOLTAGE to Shopfloor.")
