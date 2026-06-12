import re


class LogInterceptor:
    """Parses incoming log lines and translates them into structured state change events."""

    def __init__(
        self,
        on_cycle_start=None,
        on_step_start=None,
        on_delay_start=None,
        on_step_result=None,
        on_delay_finish=None,
        on_block_skip=None,
    ) -> None:
        self.on_cycle_start = on_cycle_start
        self.on_step_start = on_step_start
        self.on_delay_start = on_delay_start
        self.on_step_result = on_step_result
        self.on_delay_finish = on_delay_finish
        self.on_block_skip = on_block_skip

    def feed_line(self, message: str) -> None:
        """Parses a log line and fires appropriate callbacks if matches are found."""
        # Detect starting test cycle to reset item status
        cycle_match = re.search(r"Starting Test Cycle (\d+) / (\d+)", message)
        if cycle_match:
            if self.on_cycle_start:
                self.on_cycle_start(int(cycle_match.group(1)), int(cycle_match.group(2)))
            return

        # Match standard test item start signatures
        start_match = re.search(r"\b(\d+)\s+sapas\s+(.+)$", message)
        if start_match:
            if self.on_step_start:
                runner_index = f"{int(start_match.group(1)):02d}"
                self.on_step_start(runner_index)
            return

        # Match structural dynamic delay triggers
        delay_match = re.search(r"Start delay:\s+(.+?)\s+seconds", message)
        if delay_match:
            if self.on_delay_start:
                self.on_delay_start(delay_match.group(1).strip())
            return

        # Match termination tracking outputs
        result_match = re.search(r"\[Item\]:\s+(.+?)\s+\|\s+code=([-\d]+)", message)
        if result_match:
            if self.on_step_result:
                self.on_step_result(result_match.group(1).strip(), int(result_match.group(2)))
            return

        # Catch delay end confirmations
        if "Delay finished." in message:
            if self.on_delay_finish:
                self.on_delay_finish()
            return

        # Intercept condition failures for conditionally skipped block sequences
        if "Skipping block..." in message:
            if self.on_block_skip:
                self.on_block_skip()
            return
