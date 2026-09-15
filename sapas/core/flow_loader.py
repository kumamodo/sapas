from pathlib import Path

VALID_BLOCK_COMMANDS = {'start', 'stop', 'on_fail', 'end'}
VALID_MAIN_COMMANDS = {'verify', 'action', 'delay', 'prompt', 'cycle', 'if', 'end_if'}
VALID_FAIL_COMMANDS = {'action', 'delay', 'prompt', 'if', 'end_if'}


class FlowLoader:
    def __init__(self):
        pass

    def load_flow(self, flow_file_path: str):
        """
        Parses and performs static syntax validation on the .flow file.
        Extracts test cycles, main flow, and failure cleanup flow.
        """
        main_test_list = []
        failure_cleanup_list = []
        cycle_count = 1

        is_inside_main = False
        is_inside_fail = False

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
                    continue
                elif command == 'stop':
                    is_inside_main = False
                    continue
                elif command == 'on_fail':
                    is_inside_fail = True
                    is_inside_main = False
                    continue
                elif command == 'end':
                    is_inside_fail = False
                    continue

                if is_inside_main:
                    if command not in VALID_MAIN_COMMANDS:
                        valid_list = ', '.join(sorted(VALID_MAIN_COMMANDS))
                        raise ValueError(
                            f"[Flow Error] {seq_path.name} (Line {line_num}): Unknown command '{command}'. "
                            f"Supported commands in main flow: {valid_list}"
                        )

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

                    failure_cleanup_list.append([command, ' '.join(arguments)])

                else:
                    raise ValueError(
                        f"[Flow Error] {seq_path.name} (Line {line_num}): Command '{command}' is outside of 'start...stop' or 'on_fail...end' block."
                    )

        return cycle_count, main_test_list, failure_cleanup_list
