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
        formatted_tag = f"[{tag:^8}]"
        full_message = f"{formatted_tag} {message}"
        self.logger.info(full_message, *args)

    def _main_process(self) -> int:
        """Encapsulates the standard error-handling workflow."""
        try:
            self.run_action()
            return 0
        except Exception as e:
            log(e)
            return 1