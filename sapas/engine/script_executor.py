import time
import uuid
import importlib.util
import inspect
import argparse
import traceback
from dataclasses import dataclass
from typing import Optional

from sapas.core.base_item import BaseItem
from sapas.core.action_item import ActionItem
from sapas.core.test_item import TestItem


@dataclass
class ExecutionResult:
    return_code: int
    success: bool
    stderr: str | None = None
    duration: float | None = None


class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(f"Argument Error: {message}")


class ScriptExecutor:
    def run_python_script(
        self,
        script_path: str,
        framework_args: Optional[object] = None,
        script_args: Optional[list[str]] = None,
        logger=None
    ) -> ExecutionResult:

        start = time.time()
        stderr_output = None
        return_code = 0

        try:
            module_name = f"test_module_{uuid.uuid4().hex}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load script: {script_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            cls_list = [
                obj for name, obj in inspect.getmembers(module)
                if inspect.isclass(obj)
                and issubclass(obj, BaseItem)
                and obj not in (BaseItem, ActionItem, TestItem)
            ]

            if not cls_list:
                raise RuntimeError("No class inheriting BaseItem found in script")

            item_cls = cls_list[0]
            # Only ActionItem and TestItem parse script arguments.
            if issubclass(item_cls, (ActionItem, TestItem)):
                parser = ThrowingArgumentParser(add_help=False)

                # Users can override this.
                item_cls.build_parser(parser)
                script_args = script_args or []
                try:
                    parsed_args = parser.parse_args(script_args)
                except RuntimeError as e:
                    # Capture the error and raise as Exception for the outer handler
                    raise e
                except SystemExit:
                    # In case something still tries to exit
                    raise RuntimeError("Argument parsing failed and attempted to exit.")

                # merge framework args
                if framework_args:
                    for attr_name, attr_value in vars(framework_args).items():
                        setattr(parsed_args, attr_name, attr_value)

                test_instance = item_cls(parsed_args)
            else:
                # TestItem
                test_instance = item_cls(framework_args)

            rc = test_instance._main_process()
            if rc is not None:
                return_code = rc
        except Exception:
            return_code = 1
            stderr_output = traceback.format_exc()
            if logger:
                logger.error(stderr_output)

        duration = time.time() - start

        return ExecutionResult(
            return_code=return_code,
            success=(return_code == 0),
            stderr=stderr_output,
            duration=duration
        )