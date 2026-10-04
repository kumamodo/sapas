from pathlib import Path

VALID_BLOCK_COMMANDS = {'start', 'stop', 'on_fail', 'final', 'end'}
VALID_MAIN_COMMANDS = {'verify', 'action', 'delay', 'prompt', 'cycle', 'if', 'else', 'end_if'}
VALID_FAIL_COMMANDS = {'action', 'delay', 'prompt', 'if', 'else', 'end_if'}
VALID_FINAL_COMMANDS = {'action', 'delay', 'prompt', 'if', 'else', 'end_if'}
MAX_IF_NESTING_DEPTH = 2


def _validate_branch_command(command: str, arguments: list[str], line_num: int, file_name: str, if_stack: list[dict]):
    if command == 'if':
        cond_str = ' '.join(arguments)
        if '==' not in cond_str:
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): Invalid IF condition '{cond_str}'. "
                f"Expected format: 'VAR == VALUE'"
            )
        if len(if_stack) >= MAX_IF_NESTING_DEPTH:
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): Maximum IF nesting depth ({MAX_IF_NESTING_DEPTH}) exceeded. "
                f"Please refactor complex branching into Python scripts or separate flows."
            )
        if_stack.append({'line': line_num, 'has_else': False, 'condition': cond_str})
    elif command == 'else':
        if not if_stack:
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): 'else' without matching 'if'."
            )
        if if_stack[-1]['has_else']:
            prev_line = if_stack[-1]['line']
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): Duplicate 'else' in the same IF block (IF opened at line {prev_line})."
            )
        if arguments:
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): 'else' does not take arguments. "
                f"Note that 'elif' / 'else if' is not supported."
            )
        if_stack[-1]['has_else'] = True
    elif command == 'end_if':
        if not if_stack:
            raise ValueError(
                f"[Flow Error] {file_name} (Line {line_num}): 'end_if' without matching 'if'."
            )
        if_stack.pop()


def _check_unclosed_if(if_stack: list[dict], line_num: int, file_name: str, block_name: str):
    if if_stack:
        unclosed = if_stack[-1]
        raise ValueError(
            f"[Flow Error] {file_name} (Line {unclosed['line']}): Unclosed IF block (missing 'end_if' before '{block_name}' at line {line_num})."
        )


class FlowLoader:
    def __init__(self):
        pass

    def load_flow(self, flow_file_path: str):
        """
        Parses and performs static syntax validation on the .flow file.
        Extracts test cycles, main flow, failure cleanup flow, and final cleanup flow.
        """
        main_test_list = []
        failure_cleanup_list = []
        final_cleanup_list = []
        cycle_count = 1

        is_inside_main = False
        is_inside_fail = False
        is_inside_final = False

        main_if_stack: list[dict] = []
        fail_if_stack: list[dict] = []
        final_if_stack: list[dict] = []

        seq_path = Path(flow_file_path)
        if not seq_path.exists():
            raise FileNotFoundError(f"Sequence file not found: {flow_file_path}")

        with seq_path.open('r', encoding='UTF-8') as file:
            for line_num, raw_line in enumerate(file, start=1):
                # Remove comments and leading/trailing whitespace.
                line = raw_line.split('#', 1)[0].strip()
                if not line:
                    continue

                # Split the command and its parameters.
                tokens = line.split()
                command = tokens[0].lower()
                arguments = tokens[1:]

                # Identify process tags.
                if command == 'start':
                    is_inside_main = True
                    is_inside_fail = False
                    is_inside_final = False
                    main_if_stack.clear()
                    continue
                elif command == 'stop':
                    _check_unclosed_if(main_if_stack, line_num, seq_path.name, 'stop')
                    is_inside_main = False
                    continue
                elif command == 'on_fail':
                    is_inside_fail = True
                    is_inside_main = False
                    is_inside_final = False
                    fail_if_stack.clear()
                    continue
                elif command == 'final':
                    is_inside_final = True
                    is_inside_main = False
                    is_inside_fail = False
                    final_if_stack.clear()
                    continue
                elif command == 'end':
                    if is_inside_fail:
                        _check_unclosed_if(fail_if_stack, line_num, seq_path.name, 'end')
                        is_inside_fail = False
                    elif is_inside_final:
                        _check_unclosed_if(final_if_stack, line_num, seq_path.name, 'end')
                        is_inside_final = False
                    continue

                if is_inside_main:
                    if command not in VALID_MAIN_COMMANDS:
                        valid_list = ', '.join(sorted(VALID_MAIN_COMMANDS))
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): Unknown command '{command}'. "
                            f"Supported commands in main flow: {valid_list}"
                        )

                    if command in ('if', 'else', 'end_if'):
                        _validate_branch_command(command, arguments, line_num, seq_path.name, main_if_stack)

                    if command == 'cycle':
                        try:
                            cycle_count = int(arguments[0])
                        except (IndexError, ValueError):
                            pass

                    main_test_list.append([command, ' '.join(arguments)])

                elif is_inside_fail:
                    if command == 'verify':
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): 'verify' is not allowed inside the on_fail block. "
                            f"Use 'action' for failure recovery or cleanup steps."
                        )

                    if command not in VALID_FAIL_COMMANDS:
                        valid_list = ', '.join(sorted(VALID_FAIL_COMMANDS))
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): Unknown command '{command}' in on_fail block. "
                            f"Supported commands in on_fail block: {valid_list}"
                        )

                    if command in ('if', 'else', 'end_if'):
                        _validate_branch_command(command, arguments, line_num, seq_path.name, fail_if_stack)

                    failure_cleanup_list.append([command, ' '.join(arguments)])

                elif is_inside_final:
                    if command == 'verify':
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): 'verify' is not allowed inside the final block. "
                            f"Use 'action' for teardown or cleanup steps."
                        )

                    if command not in VALID_FINAL_COMMANDS:
                        valid_list = ', '.join(sorted(VALID_FINAL_COMMANDS))
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): Unknown command '{command}' in final block. "
                            f"Supported commands in final block: {valid_list}"
                        )

                    if command in ('if', 'else', 'end_if'):
                        _validate_branch_command(command, arguments, line_num, seq_path.name, final_if_stack)

                    final_cleanup_list.append([command, ' '.join(arguments)])

                else:
                    raise ValueError(
                        f"[Flow Error] {seq_path.name} (Line {line_num}): Command '{command}' is outside of 'start...stop', 'on_fail...end', or 'final...end' block."
                    )

        if is_inside_main:
            raise ValueError(f"[Flow Error] {seq_path.name}: Block 'start' was never closed with 'stop'.")
        if is_inside_fail:
            raise ValueError(f"[Flow Error] {seq_path.name}: Block 'on_fail' was never closed with 'end'.")
        if is_inside_final:
            raise ValueError(f"[Flow Error] {seq_path.name}: Block 'final' was never closed with 'end'.")

        return cycle_count, main_test_list, failure_cleanup_list, final_cleanup_list
