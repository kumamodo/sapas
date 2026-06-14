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
    # Let the IDE recognize the types of sapas.link and sapas.var.
    from .runtime.connection_manager import ConnectionManager
    from .runtime.runtime import VarProxy
    link: ConnectionManager
    var: VarProxy

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
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "ctx", "link", "var", "arg",
    "TestItem", "ActionItem", "BaseItem", "Message",
    "info", "warn", "error", "sleep"
]