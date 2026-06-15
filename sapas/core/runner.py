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
from sapas.modules.log import _log, log_banner, info, warn, error
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
            info("STOP_REQUESTED detected, stopping test.", tag='RUNNER')
            return True
        if self.stop_test_file_path.is_file():
            info("stop.test detected, stopping test.", tag='RUNNER')
            return True
        return False

    def _should_abort_critical(self) -> bool:
        if not self.critical_error:
            return False
        return self.ctx.get('IS_EXCEPTION_STOP', True)

    def _execute_script_item(self, item_str: str):
        parts = shlex.split(item_str)
        if not parts:
            return None
        script_name = parts[0]
        script_args = parts[1:]

        script_path = resolve_user_script(script_name, self.project_name)
        if script_path is None:
            error(f"Script not found: {item_str}", tag='RUNNER')
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

        _log('RUNNER', 
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
        if return_code != 0 and return_code != 80:
            self.critical_error = True
            error_msg = f"{item_str} got exception!"
            if result.stderr:
                error_msg += f"\nError message: {result.stderr}"
            error(error_msg, tag='RUNNER')

        return return_code

    def _export_execution_snapshot(self):
        """
        Exports the current execution context to a YAML file for post-test analysis.
        This captures the final state of all variables after the flow completes.
        """
        snapshot_name = "runtime_snapshot.yaml"
        snapshot_path = self.time_stamp_folder / snapshot_name
        info(f"Exporting execution snapshot to: {self.time_stamp_folder}", tag='RUNNER')

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
            info(f"Execution snapshot successfully saved: {snapshot_name}", tag='RUNNER')
        except (IOError, yaml.YAMLError) as err:
            error(f"Failed to save runtime context snapshot: {err}", tag='RUNNER')

    def _cmd_delay(self, seconds_str: str):
        """
        Handle the delay command natively, supporting floating-point countdown.
        """
        try:
            sec = float(seconds_str)
        except ValueError:
            error(f"Invalid delay time: {seconds_str}", tag='RUNNER')
            return

        info(f"Start delay: {sec} seconds", tag='RUNNER')
        remaining = sec
        while remaining >= 1.0:
            if self._is_stop_requested():
                warn("Delay interrupted by stop request.", tag='RUNNER')
                return

            # Use round to handle floating-point display errors
            current_display = int(round(remaining))
            info(f"Countdown {current_display} sec...", tag='RUNNER')
            time.sleep(1)
            remaining -= 1.0
            
        # Handle the fractional part (remaining time less than 1 second).
        if remaining > 0:
            if self._is_stop_requested():
                return
            info(f"Countdown {remaining:.1f} sec...", tag='RUNNER')
            time.sleep(remaining)

        info("Delay finished.", tag='RUNNER')

    def _cmd_prompt(self, arg_str: str):
        """
        Handle the prompt command natively, displaying a custom dark-themed GUI dialog.
        """
        import argparse
        import shlex
        from sapas.core.prompt import show_operator_prompt

        class PromptParser(argparse.ArgumentParser):
            def error(self, message):
                raise ValueError(message)

        parser = PromptParser(add_help=False)
        parser.add_argument('--show', type=str, default=None)
        parser.add_argument('--text', type=str, default=None)

        image_name = None
        text_content = None

        try:
            tokens = shlex.split(arg_str)
            parsed_args, remaining = parser.parse_known_args(tokens)
            image_name = parsed_args.show
            text_content = parsed_args.text

            # Handle positional/legacy fallback (e.g. prompt plug-in-USB-disk.png "text")
            if not image_name and not text_content and remaining:
                first_arg = remaining[0]
                if first_arg.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    image_name = first_arg
                    if len(remaining) > 1:
                        text_content = remaining[1]
                else:
                    text_content = arg_str
        except Exception as e:
            warn(f"Failed parsing prompt args '{arg_str}': {e}. Treating as text.", tag='RUNNER')
            image_name = None
            text_content = arg_str

        # Resolve image path relative to the active project folder if specified
        image_path = None
        if image_name:
            image_path = self.workspace_root / self.project_name / "prompt_pictures" / image_name

        info(f"Operator Prompt triggered. Text: '{text_content or ''}', Image: '{image_name or ''}'", tag='RUNNER')
        
        # Display the prompt (this will block until closed)
        show_operator_prompt(image_path=image_path, text_content=text_content, logger=self.logger)

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
        try:
            self.logger = savelog.logger
            self.ctx.set('RUNNER_LOGGER', self.logger)

            # Log deferred deprecation warnings
            deprecation_warnings = self.ctx.get('_DEPRECATION_WARNINGS')
            if deprecation_warnings:
                for warning in deprecation_warnings:
                    warn(f"[DEPRECATION] {warning}", tag='RUNNER')

            if args.test_flow:
                station_flow_file = args.test_flow
                info(f"Using user specified flow: {station_flow_file}", tag='RUNNER')
            else:
                station_flow_file = f"{self.station_name}.flow"
                info(f"Using default station flow: {station_flow_file}", tag='RUNNER')

            self.station_flow = station_flow_file

            self.is_fail_stop = self.ctx.get('IS_FAIL_STOP', True)
            if self.is_fail_stop is False:
                # Remind the operator: fail-stop is disabled, so proceed with caution.
                warn("Warning: [IS_FAIL_STOP] is set to False. Sequence will continue on failure.", tag='RUNNER')

            station_flow_file_path = self.workspace_root / self.project_name / "flows" / station_flow_file
            self.stop_test_file_path = self.workspace_root / "output" / self.serialNumber / "stop.test"

            info(f'[PROJECT_NAME]: {self.project_name}', tag='RUNNER')
            info(f'[STATION_NAME]: {self.station_name}', tag='RUNNER')
            info(f'[STATION_FLOW]: {station_flow_file}', tag='RUNNER')

            current_cycle = 1
            is_cycle_fail = False
            has_item_fail = False
            stop_test_flag = False
            self.item_index = 0
            flow = FlowLoader()
            self.cycle, self.test_item_list, self.on_fail_list = flow.load_flow(flow_file_path=station_flow_file_path)
            
            if not self.test_item_list:
                error('NO test items assigned, stopping...', tag='RUNNER')
                return

            self.current_item = self.test_item_list[self.item_index]

            log_banner(f'[Session Start] {self.timeStamp}')
            info('[Main Flow:]:', tag='RUNNER')
            for idx, item in enumerate(self.test_item_list, 1):
                info(f'  {idx:02d}. {item}', tag='RUNNER')

            info('[Fail Flow:]:', tag='RUNNER')
            for idx, item in enumerate(self.on_fail_list, 1):
                info(f'  {idx:02d}. {item}', tag='RUNNER')

            while current_cycle <= self.cycle and not self._should_abort_critical() and not is_cycle_fail and not stop_test_flag:
                # At the start of each new iteration, reset the state for the current cycle.
                info(f"Starting Test Cycle {current_cycle} / {self.cycle}", tag='RUNNER')
                self.critical_error = False

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
                    has_item_fail = False
                    self.critical_error = False
                    item = self.test_item_list[self.item_index]
                    prefix = item[0].strip()
                    self.current_item = item[1].strip()

                    if prefix == "delay":
                        self._cmd_delay(item[1].strip())
                        self.item_index += 1
                        continue

                    if prefix == "prompt":
                        log_banner(f'{self.item_index:02d} sapas {self.current_item}')
                        start_time = time.time()
                        self._cmd_prompt(item[1].strip())
                        duration = time.time() - start_time
                        _log('RUNNER', f"[Item]: {self.current_item} | code=0 | time={duration:.2f} sec")
                        self.item_index += 1
                        continue

                    # Handle IF condition evaluation.
                    if prefix == 'if':
                        try:
                            # Parsing FACTORY_LOCATION == Chiayi
                            var_key, expected_val = [p.strip() for p in self.current_item.split('==')]
                            actual_val = str(self.ctx.get(var_key))
                            
                            info(f"[Condition]: Checking {var_key} IF ('{actual_val}' == '{expected_val}')", tag='RUNNER')
                            
                            if actual_val == expected_val:
                                # Condition met: do nothing and continue to the next line.
                                self.item_index += 1
                                continue
                            else:
                                # Condition not met: enter "find END_IF" mode.
                                info(f"[Condition]: Not match. Skipping block...", tag='RUNNER')
                                skip_depth = 1
                                while skip_depth > 0:
                                    self.item_index += 1
                                    if self.item_index >= len(self.test_item_list):
                                        error("[Error]: Missing END_IF for IF condition!", tag='RUNNER')
                                        self.critical_error = True
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
                            error(f"[Error]: IF syntax error: {self.current_item} | {e}", tag='RUNNER')
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
                    # (e.g., a 80 failure condition or a script crash).
                    if return_code == 80:
                        if prefix == 'verify':
                            warn(f"Item failure detected. Aborting...", tag='RUNNER')
                            has_item_fail = True

                    elif return_code != 0:
                        # Retrieve directly from ctx, since TestItem has already
                        # populated the most accurate ErrCode before completion.
                        err_code = self.ctx.get('ERROR_CODE') or 'UNKNOWN_ERROR_CODE'
                        err_desc = self.ctx.get('ERROR_DESCRIPTION') or 'No description provided'
                        
                        error(f"[FAILED] {self.current_item} Failed!", tag='RUNNER')
                        error(f"Error Code: {err_code} | Description: {err_desc}", tag='RUNNER')

                        # If it is a critical item (or of verify type),
                        # determine whether to abort the test.
                        if prefix == 'verify':
                            error(f"Critical failure detected. Aborting...", tag='RUNNER')
                            self.ctx.set('ERROR_CODE', 'CRITICAL')
                            has_item_fail = True
                            self.critical_error = True

                    if has_item_fail or self.critical_error:
                        warn(f'Got test item fail, Going to FAIL block!', tag='RUNNER')
                        if self.is_fail_stop:
                            is_cycle_fail = True
                            stop_test_flag = True
                        log_banner('Execute items in the FAIL block.')
                        for on_fail_item in self.on_fail_list:
                            return_code = self._run_test_script(on_fail_item[1].strip())

                        if self.critical_error:
                            error('Got a critical error!', tag='RUNNER')
                            if self._should_abort_critical():
                                break
                            else:
                                warn('IS_EXCEPTION_STOP is False, continuing despite critical error...', tag='RUNNER')

                        if stop_test_flag:
                            warn('stop testing', tag='RUNNER')
                            break
                        else:
                            warn('continue testing', tag='RUNNER')
                    # Done cruuent test item, go to next
                    self.item_index += 1
                # End of one cycle
                current_cycle += 1
                self._export_execution_snapshot()
                if current_cycle <= self.cycle and not self._should_abort_critical() and not is_cycle_fail and not stop_test_flag:
                    # Small delay between cycles for visual feedback and system stabilization
                    time.sleep(1.0)

            if self._is_stop_requested():
                warn('User stop test!', tag='RUNNER')
                self.ctx.set('ERROR_CODE', 'STOP')
            elif not self.is_fail_stop:
                self.ctx.set('ERROR_CODE', 'CHECK')

            log_banner(f"[Summary] Final status = {self.ctx.get('ERROR_CODE')}")

        finally:
            # Final Cleanup
            info("Cleaning up resources...", tag='RUNNER')
            try:
                # Assume that ConnectionManager implements a method to close all connections.
                if hasattr(self.ctx, 'link'):
                    self.ctx.link.close_all()
                info("All connections closed.", tag='RUNNER')
            except Exception as cleanup_err:
                error(f"Cleanup encountered an issue: {cleanup_err}", tag='RUNNER')

            savelog.close()
