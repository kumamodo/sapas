import argparse
from abc import ABC, abstractmethod

from sapas.core.base_item import BaseItem
from sapas.modules.log import log
from sapas.runtime.runtime import ctx


class ActionItem(BaseItem, ABC):
    """
    An execution unit with a standardized error-handling workflow.
    Users should inherit from this class and implement the action method.
    """
    def __init__(self, args: argparse.Namespace):
        self.args = args
        # Reuse the Runner’s logger directly;
        # it’s a global singleton with all configurations already set.
        self.logger = ctx.get('RUNNER_LOGGER')

    @classmethod
    def build_parser(cls, parser: argparse.ArgumentParser) -> None:
        """A hook method for subclasses to extend CLI arguments."""
        pass

    @abstractmethod
    def run_action(self) -> None:
        """Defines the concrete execution behavior."""
        ...

    def log(self, message: str, *args: any, tag: str = "ACTION") -> None:
        """
        Logs information during the test process. Supports formatted strings.
        
        Example:
            self.log("Current voltage: %sV", voltage)
        """
        if not getattr(self, '_log_deprecated_shown', False):
            self._log_impl("[DEPRECATION] self.log() is deprecated and will be removed in future versions.", tag="WARN")
            self._log_impl("             Please use self.info(), self.warn(), or self.error() instead.", tag="WARN")
            setattr(self, '_log_deprecated_shown', True)
        self._log_impl(message, *args, tag=tag)

    def _log_impl(self, message: str, *args: any, tag: str = "ACTION") -> None:
        """Internal logging implementation."""
        formatted_tag = f"[{tag:^8}]"
        full_message = f"{formatted_tag} {message}"
        self.logger.info(full_message, *args)

    def info(self, message: str, *args: any) -> None:
        """Logs an informational message."""
        self._log_impl(message, *args, tag="ACTION")

    def warn(self, message: str, *args: any) -> None:
        """Logs a warning message."""
        self._log_impl(message, *args, tag="WARN")

    def error(self, message: str, *args: any) -> None:
        """Logs an error message."""
        self._log_impl(message, *args, tag="ERROR")

    def _main_process(self) -> int:
        """Encapsulates the standard error-handling workflow."""
        ctx.set("ACTIVE_LOGGER", self.logger)
        ctx.set("ACTIVE_ITEM", self)
        try:
            self.run_action()
            return 0
        except Exception as e:
            self.error(str(e))
            return 1
        finally:
            ctx.set("ACTIVE_LOGGER", None)
            ctx.set("ACTIVE_ITEM", None)