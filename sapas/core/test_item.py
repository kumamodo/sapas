import os
import sys
import traceback
import argparse
from abc import ABC, abstractmethod

from sapas.core.base_item import BaseItem
from sapas.runtime.runtime import ctx
from sapas.core.aggregator import ResultManager
from sapas.modules.message import Message
from sapas.core.measure_proxy import MeasureProxy


class TestItem(BaseItem, ABC):
    """
    The core base class for all test execution units in the Sapas framework.

    This class provides a declarative interface for implementing automated test scripts. 
    By inheriting from TestItem, users benefit from automated CLI argument parsing, 
    standardized logging, and structured result management without writing boilerplate code.

    Attributes:
        measure_file (str): Filename for recording raw measurement values.
        result_file (str): Filename for the final processed test results (CSV).
        criteria_file (str): Reference filename containing test limits and conditions.
        logs_folder (str): Directory name where all execution artifacts will be stored.
        logs_name (str): Filename for the primary execution log.
    """

    # Declare it as None at the class level to provide IDE autocomplete hints.
    measure_file: str | None = None
    result_file: str | None = None
    criteria_file: str | None = None
    logs_folder: str | None = None
    logs_name: str | None = None

    def __init__(
        self, 
        args: argparse.Namespace, 
        *,
        measure_file: str | None = None, 
        result_file: str | None = None,
        criteria_file: str | None = None,
        logs_folder: str | None = None,
        logs_name: str | None = None
    ) -> None:
        """
        Initializes the test item and prepares the execution environment.

        The initialization process resolves configuration priorities (Arguments > Class Attributes)
        and ensures the output directory structure is created before test execution starts.

        Args:
            args (argparse.Namespace): Parsed command-line arguments.
            measure_file (str, optional): Override for the measurement filename.
            result_file (str, optional): Override for the result filename.
            criteria_file (str, optional): Override for the criteria filename.
            logs_folder (str, optional): Override for the logs directory name.
            logs_name (str, optional): Override for the log filename.

        Raises:
            ValueError: If any mandatory configuration attribute is missing.
        """
        self.args = args

        # Priority Resolution: Arguments take precedence over Class Attributes.
        self.measure_file = measure_file or getattr(self, "measure_file", None)
        self.result_file = result_file or getattr(self, "result_file", None)
        self.criteria_file = criteria_file or getattr(self, "criteria_file", None)
        self.logs_folder = logs_folder or getattr(self, "logs_folder", None)
        self.logs_name = logs_name or getattr(self, "logs_name", None)

        # Resilience Defense: Automatically handle accidental trailing commas (tuple conversion).
        for attr in ["measure_file", "result_file", "criteria_file", "logs_folder", "logs_name"]:
            val = getattr(self, attr)
            if isinstance(val, tuple):
                if len(val) > 0:
                    setattr(self, attr, str(val[0]))
                else:
                    setattr(self, attr, None)

        # 3. Mandatory Configuration Validation.
        required = {
            "measure_file": self.measure_file,
            "result_file": self.result_file,
            "criteria_file": self.criteria_file,
            "logs_folder": self.logs_folder,
            "logs_name": self.logs_name,
        }

        missing = [name for name, val in required.items() if val is None]

        if missing:
            class_name = self.__class__.__name__
            raise ValueError(
                f"\n[Sapas] Configuration Error: Script class '{class_name}' is missing required attributes.\n"
                f"  Missing: {', '.join(missing)}\n\n"
                f"Please define these attributes directly within your class (no __init__ required).\n"
                f"Example of a valid configuration:\n"
                f"--------------------------------------------------\n"
                f"class {class_name}(TestItem):\n"
                f"    measure_file  = \"{class_name.lower()}_measure.txt\"\n"
                f"    result_file   = \"{class_name.lower()}_result.csv\"\n"
                f"    criteria_file = \"{class_name.lower()}_criteria.csv\"\n"
                f"    logs_folder   = \"{class_name.upper()}_LOGS\"\n"
                f"    logs_name     = \"{class_name.lower()}.log\"\n"
                f"--------------------------------------------------"
            )

        # Initialize Workspace and Output Directories.
        workspace_root = ctx.get('WORKSPACE_ROOT')
        self.outputFolder = os.path.join(
            workspace_root, 'output', args.serialNumber, args.timeStamp, self.logs_folder
        )
        os.makedirs(self.outputFolder, exist_ok=True)

        # Initialize the ResultManager
        self.pResult = ResultManager(self.outputFolder, self.criteria_file, self.measure_file)

        # Retrieve the list of criteria items from the ResultManager.
        item_names = self.pResult.get_item_names()
        
        # Create a proxy object.
        self.measure = MeasureProxy(item_names)
        self.measure_value = []

        # Initialize the log
        self.savelog = Message(os.path.join(self.outputFolder, self.logs_name), self.logs_folder, ctx.get('RUNNER_LOGGER'))
        self.logger = self.savelog.logger

        self._exception = False
        self._exception_message = None

    @classmethod
    def build_parser(cls, parser: argparse.ArgumentParser) -> None:
        """
        [Hook] Allows users to extend custom CLI arguments.
        
        Args:
            parser: The argparse parser object.
        """
        pass

    def log(self, message: str, *args: any, tag: str = "USER") -> None:
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

    def _log_impl(self, message: str, *args: any, tag: str = "USER") -> None:
        """Internal logging implementation."""
        formatted_tag = f"[{tag:^8}]"
        full_message = f"{formatted_tag} {message}"
        self.logger.info(full_message, *args)

    def info(self, message: str, *args: any) -> None:
        """Logs an informational message."""
        self._log_impl(message, *args, tag="INFO")

    def warn(self, message: str, *args: any) -> None:
        """Logs a warning message."""
        self._log_impl(message, *args, tag="WARN")

    def error(self, message: str, *args: any) -> None:
        """Logs an error message."""
        self._log_impl(message, *args, tag="ERROR")

    @abstractmethod
    def run_test(self) -> None:
        """
        [Required] Implements the concrete test logic.
        
        Override this method in subclasses. If an exception occurs during execution,
        it will be automatically caught by the parent class's main_process.
        """
        ...

    def _make_result(self) -> int:
        """
        [Internal] Consolidates measurement data and persists results to storage.

        This method synchronizes the MeasureProxy data with the CSV structure,
        generates result files, and updates the global execution context with 
        failure codes and descriptions.

        Returns:
            int: Execution status code (0 for PASS, 8080 for FAIL).
        """
        # Before saving, convert the proxy dictionary back
        # into a list that matches the CSV column order.
        self.measure_value = self.measure.to_list()

        # Write the test values to the result file.
        ret = self.pResult.process_test_results(self.measure_file, self.result_file, self.measure_value)
        
        # Populate the context (ctx) with the structured data prepared
        # by ResultManager, so that the Runner can access it directly.
        existing_data = ctx.get('TEST_DATA_STRING') or ""
        ctx.set('TEST_DATA_STRING', existing_data + self.pResult.shopfloor_string)
        
        ctx.set('ERROR_CODE', self.pResult.first_fail_code)
        if self.pResult.first_fail_code != "PASS":
            ctx.set('ERROR_DESCRIPTION', self.pResult.first_fail_desc)
        return ret

    def _main_process(self):
        ctx.set("ACTIVE_LOGGER", self.logger)
        try:
            self.run_test()
        except Exception as err:
            self._exception = True
            self._exception_message = str(err)
            sys.stderr.write("\033[91m")
            traceback.print_exc()
            sys.stderr.write("\033[0m")
        finally:
            ctx.set("ACTIVE_LOGGER", None)
            self.savelog.close()
            result_code = self._make_result()

        # If an exception occurs, force return 1;
        # otherwise return the result determined by make_result
        return 1 if self._exception else result_code