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
        # NOTE: In real-world scripts, you do NOT need to read `self.sapas_tag` in your code.
        # The connected hardware or instruments will naturally return different physical readings 
        # at different times, and Sapas will handle mapping them to the correct CSV slots automatically.
        #
        # In this software-only demo, we read `self.sapas_tag` to simulate different fake values
        # (5.05V vs 12.12V) for FIRST vs SECOND execution.
        # Check `example/Alishan/flows/function.flow` to see how these tags are specified in the flow.
        measured_voltage = 5.05 if self.sapas_tag == "FIRST" else 12.12
        sapas.info(f"[{self.sapas_tag}] Measured Voltage: {measured_voltage}V")

        # Set the measurement value.
        # Sapas automatically maps "VOLTAGE" to "VOLTAGE_FIRST" or "VOLTAGE_SECOND" 
        # in the criteria CSV (defined as "VOLTAGE_{}") based on the active --sapas-tag.
        sapas.measure.VOLTAGE = measured_voltage
        sapas.info(f"[{self.sapas_tag}] Saved VOLTAGE to Shopfloor.")
