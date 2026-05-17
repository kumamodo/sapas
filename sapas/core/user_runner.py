from pathlib import Path
import importlib.util
import inspect
from argparse import Namespace
from datetime import datetime

from sapas.runtime.runtime import ctx
from sapas import BaseItem
from sapas import ActionItem
from sapas import TestItem
from sapas.modules.message import Message
from sapas.engine.script_executor import ScriptExecutor
from sapas.core.utils import resolve_user_script


def run_user_script(script_name: str, cli_args=None, user_args=None):
    """
    Execute a single user script, reusing the already-initialized rt.ctx from cli.py with priority.
    """
    if isinstance(cli_args, Namespace):
        framework_args = cli_args

    # Handle user-defined parameters.
    # If cli.py passes in remaining_args, use it; otherwise use an empty list.
    final_user_args = user_args if user_args is not None else []

    from sapas.runtime.runtime import ctx as global_ctx
    
    # If global_ctx already contains data (meaning it was passed in from cli.py).
    if global_ctx.get("WORKSPACE_ROOT"):
        logger_name = "UserRunner"
        project_name = global_ctx.get("PROJECT_NAME")
        workspace = Path(global_ctx.get("WORKSPACE_ROOT"))
        # Reuse the logger initialized by cli.py.
        logger = global_ctx.get("RUNNER_LOGGER")

    script_path = resolve_user_script(script_name, project_name)

    output_folder = workspace / "output" / framework_args.serialNumber / framework_args.timeStamp
    output_folder.mkdir(parents=True, exist_ok=True)
    log_path = workspace / "output" / framework_args.serialNumber / f"{framework_args.serialNumber}.log"
    logger = Message(str(log_path), 'UserScript').logger

    ctx.set("RUNNER_LOGGER", logger)

    # Dynamically load the user script class.
    spec = importlib.util.spec_from_file_location("user_script", str(script_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Only select non-abstract, non-base subclasses.
    cls_list = [
        obj for name, obj in inspect.getmembers(module)
        if inspect.isclass(obj)
        and issubclass(obj, BaseItem)
        and obj not in (BaseItem, ActionItem, TestItem)
    ]

    if not cls_list:
        raise RuntimeError("No class inheriting BaseItem found in script")

    executor = ScriptExecutor()
    result = executor.run_python_script(
        str(script_path),
        framework_args=framework_args,
        script_args=final_user_args,
        logger=logger
    )

    logger.info(f"User script [{script_path.name}] finished")
    logger.info(f"Return code: {result.return_code}, Success: {result.success}")
    logger.info(f"Output folder: {output_folder}")
    logger.info(f"Log path: {log_path}")

    logger.info("Cleaning up resources...")
    try:
        # Assume that ConnectionManager provides a method to close all connections.
        if hasattr(ctx, 'link'):
            ctx.link.close_all()
        logger.info("All connections closed.")
    except Exception as cleanup_err:
        logger.debug(f"Cleanup encountered an issue: {cleanup_err}")

    return result