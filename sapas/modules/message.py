import logging
from rich.logging import RichHandler
from rich.console import Console


class PropagateHandler(logging.Handler):
    """Forward log events to another logger"""
    def __init__(self, target_logger):
        super().__init__()
        self.target_logger = target_logger

    def emit(self, record):
        # Directly let the target logger handle this record.
        self.target_logger.handle(record)


# Add this custom Formatter above the Message class.
class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        # First format the message using the original method.
        save_msg = record.msg
        # Get the fully formatted single-line string
        # (including timestamp, log level, etc.).
        formatted = super().format(record)
        
        # Extract the prefix (e.g., "2026-03-27... - INFO - ").
        # Subtract the original message content from the
        # full formatted string; the remainder is the prefix.
        prefix = formatted.split(str(record.message))[0]
        
        # Replace every newline character in the message with “newline + prefix”.
        res = formatted.replace("\n", "\n" + prefix)
        return res


class Message:
    def __init__(self, logPath=None, logger_name="sapas", propagate_to=None):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

        # Switch to using our custom MultiLineFormatter.
        formatter = MultiLineFormatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )

        self._own_handlers = []

        # Prevent duplicate handlers
        if not self.logger.handlers and logPath:
            file_handler = logging.FileHandler(logPath, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self._own_handlers.append(file_handler)

        # Propagate the log to another logger.
        if propagate_to:
            ph = PropagateHandler(propagate_to)
            self.logger.addHandler(ph)
            self._own_handlers.append(ph)
            # It has already been forwarded to another logger;
            # disable propagation to avoid duplicate output in the terminal.
            self.logger.propagate = False
        else:
            # Propagate to root
            if self.logger.name != "root":
                self.logger.propagate = True

        # Replace the root logger’s console output with RichHandler.
        root_logger = logging.getLogger()

        if not any(isinstance(h, RichHandler) for h in root_logger.handlers):
            # RichHandler automatically handles timestamps and log levels,
            # so no additional formatter is needed.
            rich_handler = RichHandler(
                # Set a wider width to prevent table wrapping.
                console=Console(width=150),
                rich_tracebacks=True,
                markup=False,
                # Set it to False if you don’t want to see
                # log.py:line_number on the right side.
                show_path=False
            )
            root_logger.addHandler(rich_handler)

    def close(self):
        for handler in self._own_handlers:
            handler.close()
            self.logger.removeHandler(handler)
        self._own_handlers.clear()
