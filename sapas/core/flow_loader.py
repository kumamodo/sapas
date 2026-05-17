from pathlib import Path


class FlowLoader:
    def __init__(self):
        pass

    def load_flow(self, flow_file_path: str):
        """
        Parses the .flow file to extract test cycles, main flow, and failure flow.
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
            for raw_line in file:
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
                    continue
                elif command == 'stop':
                    is_inside_main = False
                    continue
                elif command == 'on_fail':
                    is_inside_fail = True
                    continue
                elif command == 'end':
                    is_inside_fail = False
                    continue

                if is_inside_main:
                    if command == 'cycle':
                        try:
                            cycle_count = int(arguments[0])
                        except (IndexError, ValueError):
                            pass
                    
                    # Store the commands in a list (including cycle commands,
                    # so the Runner can also evaluate them).
                    main_test_list.append([command, ' '.join(arguments)])

                elif is_inside_fail:
                    failure_cleanup_list.append([command, ' '.join(arguments)])

        return cycle_count, main_test_list, failure_cleanup_list
