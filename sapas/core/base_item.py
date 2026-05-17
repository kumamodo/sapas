import argparse
from abc import ABC, abstractmethod


class BaseItem(ABC):
    """The abstract base class of the framework, defining the fundamental structure for all execution units."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    @abstractmethod
    def _main_process(self) -> int:
        """The main execution entry point that must be implemented by subclasses."""
        ...