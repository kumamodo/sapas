# # sapas/__init__.py

from sapas.core.action_item import ActionItem
from sapas.core.test_item import TestItem
from sapas.core.base_item import BaseItem
from sapas.modules.message import Message
from sapas.modules.log import info, warn, error
from sapas.runtime.runtime import ctx
from sapas.core.builtins import sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Let the IDE recognize the types of sapas.link, sapas.var, and sapas.measure.
    from .runtime.connection_manager import ConnectionManager
    from .runtime.runtime import VarProxy
    from .core.measure_proxy import MeasureProxy
    link: ConnectionManager
    var: VarProxy
    measure: MeasureProxy

def arg(*args, **kwargs):
    """
    Decorator to register custom arguments for a TestItem or ActionItem.
    Usage:
        @sapas.arg("--my-param", type=str, help="Description")
        class MyTest(TestItem):
            ...
    """
    def decorator(cls):
        if not hasattr(cls, '_custom_args'):
            cls._custom_args = []
        # Store arguments at the beginning to maintain relative order if stacked
        cls._custom_args.insert(0, (args, kwargs))
        return cls
    return decorator

def __getattr__(name):
    if name == "link":
        return ctx.link
    if name == "var":
        return ctx.var
    if name == "measure":
        active_item = ctx.get("ACTIVE_ITEM")
        if active_item is None:
            raise RuntimeError("No active TestItem running in execution context. Cannot access sapas.measure.")
        measure = getattr(active_item, "_measure_proxy", None)
        if measure is None:
            raise RuntimeError("The active item does not have a measure proxy. Only TestItem supports measurements.")
        return measure
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "ctx", "link", "var", "measure", "arg",
    "TestItem", "ActionItem", "BaseItem", "Message",
    "info", "warn", "error", "sleep"
]