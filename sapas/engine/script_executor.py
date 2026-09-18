import io
import sys
import time
import uuid
import threading
import importlib.util
import inspect
import argparse
import traceback
import warnings
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from sapas.core.base_item import BaseItem
from sapas.core.action_item import ActionItem
from sapas.core.test_item import TestItem
from sapas.modules.log import _thread_local


class StdoutRedirector(io.TextIOBase):
    """
    Redirects standard stdout (print statements) to Sapas logger with [ PRINT ] tag.
    Uses a thread-local recursion guard to prevent infinite logging loops.
    """
    def __init__(self, original_stdout, log_func):
        self.original_stdout = original_stdout
        self.log_func = log_func
        self._buffer = ""

    def write(self, s):
        if not s:
            return 0

        # Anti-recursion guard: If logger itself is outputting, pass directly to original_stdout
        if getattr(_thread_local, 'is_logging', False):
            return self.original_stdout.write(s)

        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line_str = line.rstrip("\r")
            if line_str:
                _thread_local.is_logging = True
                try:
                    self.log_func("PRINT", line_str)
                finally:
                    _thread_local.is_logging = False
        return len(s)

    def flush(self):
        if getattr(_thread_local, 'is_logging', False):
            return self.original_stdout.flush()

        if self._buffer.rstrip("\r"):
            _thread_local.is_logging = True
            try:
                self.log_func("PRINT", self._buffer.rstrip("\r"))
            finally:
                _thread_local.is_logging = False
            self._buffer = ""


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
            # Extract and strip --sapas-tag from script_args
            sapas_tag = None
            if script_args:
                new_args = []
                i = 0
                while i < len(script_args):
                    if script_args[i] == '--sapas-tag':
                        if i + 1 < len(script_args):
                            sapas_tag = script_args[i + 1]
                            i += 2
                            continue
                        else:
                            raise RuntimeError("Error: --sapas-tag requires a value.")
                    new_args.append(script_args[i])
                    i += 1
                script_args = new_args

            try:
                from sapas.runtime.runtime import ctx
                ctx.set("CURRENT_SAPAS_TAG", sapas_tag)
            except Exception:
                pass

            from sapas.core.utils import setup_sapas_sys_path
            script_path_obj = Path(script_path).resolve()
            setup_sapas_sys_path(script_path_obj)

            module_name = f"test_module_{uuid.uuid4().hex}"
            spec = importlib.util.spec_from_file_location(module_name, str(script_path_obj))
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Cannot load script: {script_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            cls_list = [
                obj for name, obj in inspect.getmembers(module)
                if inspect.isclass(obj)
                and issubclass(obj, BaseItem)
                and obj not in (BaseItem, ActionItem, TestItem)
                and getattr(obj, '__module__', None) == module.__name__
            ]

            if not cls_list:
                raise RuntimeError("No class inheriting BaseItem found in script")

            item_cls = cls_list[0]
            # Only ActionItem and TestItem parse script arguments.
            if issubclass(item_cls, (ActionItem, TestItem)):
                parser = ThrowingArgumentParser(add_help=False)

                # Process Decorator-based arguments (@sapas.arg)
                if hasattr(item_cls, '_custom_args'):
                    for a, kw in item_cls._custom_args:
                        parser.add_argument(*a, **kw)

                # Process legacy build_parser method (Backward Compatibility)
                # Check if the user has overridden the default build_parser
                base_cls = TestItem if issubclass(item_cls, TestItem) else ActionItem
                if item_cls.build_parser.__func__ is not base_cls.build_parser.__func__:
                    msg = (
                        f"\n[DEPRECATION WARNING] In {script_path}:\n"
                        "build_parser() is deprecated and will be removed in a future version.\n"
                        "Please use the @sapas.arg decorator instead for a cleaner syntax.\n"
                    )
                    # Use print or logger to ensure visibility since DeprecationWarning 
                    # is often silenced by default Python filters.
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)

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

            old_stdout = sys.stdout
            from sapas.modules.log import _log
            redirector = StdoutRedirector(old_stdout, _log)
            sys.stdout = redirector
            try:
                rc = test_instance._main_process()
                if rc is not None:
                    return_code = rc
            finally:
                redirector.flush()
                sys.stdout = old_stdout
        except SystemExit as e:
            code = 0 if (e.code is None or e.code == 0) else (e.code if isinstance(e.code, int) else 1)
            return_code = code
            if code != 0:
                stderr_output = f"Script exited via sys.exit({e.code})"
                if logger:
                    logger.error(stderr_output)
            else:
                if logger:
                    logger.info("Script completed via sys.exit(0)")
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