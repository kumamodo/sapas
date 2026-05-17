# # sapas/__init__.py

from sapas.core.action_item import ActionItem
from sapas.core.test_item import TestItem
from sapas.core.base_item import BaseItem
from sapas.modules.message import Message
from sapas.runtime.runtime import ctx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Let the IDE recognize the types of sapas.link and sapas.var.
    from .runtime.connection_manager import ConnectionManager
    from .runtime.runtime import VarProxy
    link: ConnectionManager
    var: VarProxy

def __getattr__(name):
    if name == "link":
        return ctx.link
    if name == "var":
        return ctx.var
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "ctx", "link", "var",
    "TestItem", "ActionItem", "BaseItem", "Message"
]