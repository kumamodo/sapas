import sys
import time
import yaml
import shlex

from argparse import Namespace
from datetime import datetime
from pathlib import Path
from sapas.core.flow_loader import FlowLoader
from sapas.modules.message import Message
from sapas.engine.script_executor import ScriptExecutor
from sapas.modules.log import log, log_banner
from sapas.core.utils import resolve_user_script


class Runner():
    def __init__(self, context):
        self.ctx = context
        self.executor = ScriptExecutor()

        raw_root = self.ctx.get('WORKSPACE_ROOT')
        self.workspace_root = Path(raw_root) if raw_root else Path.cwd()

        self.project_name = self.ctx.get("PROJECT_NAME")
        self.station_name = self.ctx.get("STATION_NAME")

    def _is_stop_requested(self) -> bool:
        if self.ctx.get('STOP_REQUESTED', False):
            log('RUNNER', "STOP_REQUESTED detected, stopping test.")
            return True
        if self.stop_test_file_path.is_file():
            log('RUNNER', "stop.test detected, stopping test.")
            return True
        return False

    def _execute_script_item(self, item_str: str):
        parts = shlex.split(item_str)
        script_name = parts[0]
        script_args = parts[1:]

        script_path = resolve_user_script(script_name, self.project_name)
        if script_path is None:
            log('RUNNER', f"Script not found: {item_str}")
            self.critical_error = True
            return None

        # create a proper Namespace for user script
        framework_args = Namespace(
            serialNumber=self.serialNumber,
            timeStamp=self.timeStamp
        )

        result = self.executor.run_python_script(
            str(script_path),
            framework_args=framework_args,
            script_args=script_args,
            logger=self.logger
        )

        log('RUNNER', 
            f"[Item]: {item_str} | "
            f"code={result.return_code} | "
            f"time={result.duration:.2f} sec"
        )
        return result

    def _run_test_script(self, item_str: str):
        result = self._execute_script_item(item_str)
        if result is None:
            return -1

        return_code = result.return_code
        # if not result.success:
        if return_code == 1:
            self.critical_error = True
            error_msg = f"{item_str} got exception!"
            if result.stderr:
                error_msg += f"\nError message: {result.stderr}"
            log('RUNNER', error_msg)

        return return_code

    def _export_execution_snapshot(self):
        """
        Exports the current execution context to a YAML file for post-test analysis.
        This captures the final state of all variables after the flow completes.
        """
        snapshot_name = "runtime_snapshot.yaml"
        snapshot_path = self.time_stamp_folder / snapshot_name
        log('RUNNER', f"Exporting execution snapshot to: {self.time_stamp_folder}")

        try:
            self.time_stamp_folder.mkdir(parents=True, exist_ok=True)
            execution_snapshot = self.ctx.to_dict()
            with open(snapshot_path, 'w', encoding='utf-8') as yaml_file:
                yaml.dump(
                    execution_snapshot,
                    yaml_file,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=True
                )
            log('RUNNER', f"Execution snapshot successfully saved: {snapshot_name}")
        except (IOError, yaml.YAMLError) as err:
            log('RUNNER', f"[Error] Failed to save runtime context snapshot: {err}")

    def _cmd_delay(self, seconds_str: str):
        """
        Handle the delay command natively, supporting floating-point countdown.
        """
        try:
            sec = float(seconds_str)
        except ValueError:
            log('RUNNER', f"Invalid delay time: {seconds_str}")
            return

        log('RUNNER',f"Start delay: {sec} seconds")
        remaining = sec
        while remaining >= 1.0:
            # Use round to handle floating-point display errors
            current_display = int(round(remaining))
            log('RUNNER',f"Countdown {current_display} sec...")
            time.sleep(1)
            remaining -= 1.0
            
        # Handle the fractional part (remaining time less than 1 second).
        if remaining > 0:
            log('RUNNER',f"Countdown {remaining:.1f} sec...")
            time.sleep(remaining)

        log('RUNNER',"Delay finished.")

    def execute_flows(self, args):
        self.critical_error = False
        self.error_code = None
        self.item_index = 0

        self.serialNumber = args.serialNumber
        self.timeStamp = args.timeStamp

        self.output_root = self.workspace_root / "output"
        self.main_log_path = self.output_root / self.serialNumber
        self.time_stamp_folder = self.main_log_path / self.timeStamp
        self.time_stamp_folder.mkdir(parents=True, exist_ok=True)

        savelog = Message(str(self.main_log_path / f"{self.serialNumber}.log"), 'Runner')
        self.logger = savelog.logger
        self.ctx.set('RUNNER_LOGGER', self.logger)

        if args.test_flow:
            station_flow_file = args.test_flow
            log('RUNNER', f"Using user specified flow: {station_flow_file}")
        else:
            station_flow_file = f"{self.station_name}.flow"
            log('RUNNER', f"Using default station flow: {station_flow_file}")

        self.station_flow = station_flow_file

        self.is_fail_stop = self.ctx.get('IS_FAIL_STOP', True)
        if self.is_fail_stop is False:
            # Remind the operator: fail-stop is disabled, so proceed with caution.
            log('RUNNER', "Warning: [IS_FAIL_STOP] is set to False. Sequence will continue on failure.")

        station_flow_file_path = self.workspace_root / self.project_name / "flows" / station_flow_file
        self.stop_test_file_path = self.workspace_root / "output" / self.serialNumber / "stop.test"

        log('RUNNER', f'[PROJECT_NAME]: {self.project_name}')
        log('RUNNER', f'[STATION_NAME]: {self.station_name}')
        log('RUNNER', f'[STATION_FLOW]: {station_flow_file}')

        current_cycle = 1
        is_cycle_fail = False
        has_item_fail = False
        stop_test_flag = False
        self.item_index = 0
        flow = FlowLoader()
        self.cycle, self.test_item_list, self.on_fail_list = flow.load_flow(flow_file_path=station_flow_file_path)
        self.current_item = self.test_item_list[self.item_index]

        log_banner(f'[Session Start] {self.timeStamp}')
        log('RUNNER', '[Main Flow:]:')
        for idx, item in enumerate(self.test_item_list, 1):
            log('RUNNER', f'  {idx:02d}. {item}')

        log('RUNNER', '[Fail Flow:]:')
        for idx, item in enumerate(self.on_fail_list, 1):
            log('RUNNER', f'  {idx:02d}. {item}')

        if not self.test_item_list:
            log('RUNNER', 'NO test items assigned, stopping...')
            sys.exit(0)

        while current_cycle <= self.cycle and not self.critical_error and not is_cycle_fail and not stop_test_flag:
            # At the start of each new iteration, reset the state for the current cycle.
            log('RUNNER', f"Starting Test Cycle {current_cycle} / {self.cycle}")

            # Reset the context to clear all per-cycle runtime variables.
            self.ctx.reset()
            
            # Re-initialize cycle status to Fail-Safe state.
            self.ctx.set('ERROR_CODE', 'FAIL')
            self.ctx.set('ERROR_DESCRIPTION', 'Test initialized but not completed')
            
            stop_test_flag = False
            if current_cycle >= 2:
                self.timeStamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.time_stamp_folder = self.main_log_path / self.timeStamp
            self.item_index = 0
            if self._is_stop_requested():
                break
            
            while self.item_index < len(self.test_item_list):
                stop_test_flag = False
                item = self.test_item_list[self.item_index]
                prefix = item[0].strip()
                self.current_item = item[1].strip()

                if prefix == "delay":
                    self._cmd_delay(item[1].strip())
                    self.item_index += 1
                    continue

                # Handle IF condition evaluation.
                if prefix == 'if':
                    try:
                        # Parsing FACTORY_LOCATION == Chiayi
                        var_key, expected_val = [p.strip() for p in self.current_item.split('==')]
                        actual_val = str(self.ctx.get(var_key))
                        
                        log('RUNNER', f"[Condition]: Checking {var_key} IF ('{actual_val}' == '{expected_val}')")
                        
                        if actual_val == expected_val:
                            # Condition met: do nothing and continue to the next line.
                            self.item_index += 1
                            continue
                        else:
                            # Condition not met: enter "find END_IF" mode.
                            log('RUNNER', f"[Condition]: Not match. Skipping block...")
                            skip_depth = 1
                            while skip_depth > 0:
                                self.item_index += 1
                                if self.item_index >= len(self.test_item_list):
                                    log('RUNNER', "[Error]: Missing END_IF for IF condition!")
                                    break
                                
                                next_item_prefix = self.test_item_list[self.item_index][0].strip().upper()
                                if next_item_prefix == 'IF':
                                    # Encounter a nested IF.
                                    skip_depth += 1
                                elif next_item_prefix == 'END_IF':
                                    # Encounter the corresponding end marker.
                                    skip_depth -= 1
                            # Skip the final END_IF.
                            self.item_index += 1
                            continue
                    except Exception as e:
                        log('RUNNER', f"[Error]: IF syntax error: {self.current_item} | {e}")
                        self.critical_error = True
                        break

                # Handle the END_IF marker.
                if prefix == 'end_if':
                    # If execution reaches here normally, 
                    # it means the IF block has been fully processed; simply skip the marker.
                    self.item_index += 1
                    continue

                if self._is_stop_requested():
                    break

                if prefix == 'cycle':
                    self.item_index += 1
                    continue

                log_banner(f'{self.item_index:02d} sapas {self.current_item}')
                return_code = self._run_test_script(self.current_item)

                # Any value other than 0 (PASS) indicates an issue
                # (e.g., a 8080 failure condition or a script crash).
                if return_code == 8080:
                    if prefix == 'verify':
                        log('RUNNER', f"Item failure detected. Aborting...")
                        has_item_fail = True

                elif return_code != 0:
                    # Retrieve directly from ctx, since TestItem has already
                    # populated the most accurate ErrCode before completion.
                    err_code = self.ctx.get('ERROR_CODE') or 'UNKNOWN_ERROR_CODE'
                    err_desc = self.ctx.get('ERROR_DESCRIPTION') or 'No description provided'
                    
                    log('RUNNER', f"[FAILED] {self.current_item} Failed!")
                    log('RUNNER', f"Error Code: {err_code} | Description: {err_desc}")

                    # If it is a critical item (or of verify type),
                    # determine whether to abort the test.
                    if prefix == 'verify':
                        log('RUNNER', f"Critical failure detected. Aborting...")
                        self.ctx.set('ERROR_CODE', 'CRITICAL')
                        has_item_fail = True
                        self.critical_error = True

                if prefix == 'action' and return_code == 0:
                    self.ctx.set('ERROR_CODE', 'PASS')

                if has_item_fail or self.critical_error:
                    log('RUNNER', f'Got test item fail, Going to FAIL block!')
                    if self.is_fail_stop:
                        is_cycle_fail = True
                        stop_test_flag = True
                    log_banner('Execute items in the FAIL block.')
                    for on_fail_item in self.on_fail_list:
                        return_code = self._run_test_script(on_fail_item[1].strip())

                    if self.critical_error:
                        log('RUNNER', 'Got a critical error!')
                        if prefix == 'action':
                            self.ctx.set('ERROR_CODE', 'CRITICAL')
                        break

                    if stop_test_flag:
                        log('RUNNER', 'stop testing')
                        break
                    else:
                        log('RUNNER', 'continue testing')
                # Done cruuent test item, go to next
                self.item_index += 1
            # End of one cycle
            current_cycle += 1
            self._export_execution_snapshot()
            if current_cycle <= self.cycle and not self.critical_error and not is_cycle_fail and not stop_test_flag:
                # Small delay between cycles for visual feedback and system stabilization
                time.sleep(1.0)

        if self._is_stop_requested():
            log('RUNNER', 'User stop test!')
            self.ctx.set('ERROR_CODE', 'STOP')
        elif not self.is_fail_stop:
            self.ctx.set('ERROR_CODE', 'CHECK')

        log_banner(f"[Summary] Final status = {self.ctx.get('ERROR_CODE')}")

        # Final Cleanup
        log('RUNNER', "Cleaning up resources...")
        try:
            # Assume that ConnectionManager implements a method to close all connections.
            if hasattr(self.ctx, 'link'):
                self.ctx.link.close_all()
            log('RUNNER', "All connections closed.")
        except Exception as cleanup_err:
            log('RUNNER', f"Cleanup encountered an issue: {cleanup_err}")

        savelog.close()
