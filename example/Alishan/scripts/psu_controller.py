import sapas
from sapas import ActionItem


@sapas.arg("--state", type=str, default="cycle", choices=["on", "off", "cycle"], help="Power state: on, off, or cycle (demo)")
@sapas.arg("--voltage", type=float, default=12.0, help="Target voltage in Volts")
@sapas.arg("--current", type=float, default=2.0, help="Target current limit in Amperes")
class PsuController(ActionItem):
    """
    Controls DC Power Supply output state, voltage, and current limit.
    Usage in flow or CLI:
      - Turn ON  : action psu_controller.py --state on --voltage 12.0 --current 2.0
      - Turn OFF : action psu_controller.py --state off
      - Demo/Test: action psu_controller.py --state cycle --voltage 12.0 --current 2.0
    """

    def run_action(self):
        psu = sapas.link.get("main_psu")
        state = str(self.args.state).lower()
        voltage = float(self.args.voltage)
        current = float(self.args.current)

        if state == "on":
            sapas.info(f"[PSU] Powering ON -> Voltage: {voltage} V, Current Limit: {current} A")
            psu.output_on(voltage=voltage, current=current)
            sapas.sleep(0.5)
            sapas.info(f"[PSU] Measured Voltage: {psu.measure_voltage()} V")
            sapas.info(f"[PSU] Measured Current: {psu.measure_current()} A")

        elif state == "off":
            sapas.info("[PSU] Powering OFF...")
            psu.output_off()
            sapas.info("[PSU] Output is now OFF")

        elif state == "cycle":
            # Demonstration cycle: turn ON, measure, wait 3 seconds, turn OFF
            sapas.info(f"[PSU Cycle] Powering ON -> Voltage: {voltage} V, Current Limit: {current} A")
            psu.output_on(voltage=voltage, current=current)
            sapas.sleep(1)
            sapas.info(f"[PSU Cycle] Measured Voltage: {psu.measure_voltage()} V")
            sapas.info(f"[PSU Cycle] Measured Current: {psu.measure_current()} A")
            sapas.info("[PSU Cycle] Holding power for 3 seconds...")
            sapas.sleep(3)
            sapas.info("[PSU Cycle] Powering OFF...")
            psu.output_off()
            sapas.info("[PSU Cycle] Completed successfully.")
