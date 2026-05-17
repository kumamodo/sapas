from typing import Any, Dict, Optional, TYPE_CHECKING

_CURRENT_CONTEXT = None


class LinkManager:
    # Hint: let the IDE know what methods link provides.
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...


class VarProxy:
    # A proxy class dedicated to handling sapas.var.get/set.
    def get(self, key: str, default: Any = None) -> Any:
        if _CURRENT_CONTEXT is None:
            raise RuntimeError("ExecutionContext not initialized.")
        return _CURRENT_CONTEXT.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if _CURRENT_CONTEXT is None:
            raise RuntimeError("ExecutionContext not initialized.")
        _CURRENT_CONTEXT.set(key, value)

    def require(self, key: str) -> Any:
        value = self.get(key)
        if value is None:
            raise RuntimeError(f"Required variable '{key}' not found.")
        return value


class _CtxProxy:
    def __init__(self):
        # Initialize the variable proxy.
        self.var = VarProxy()

    @property
    def link(self):
        if _CURRENT_CONTEXT is None:
            raise RuntimeError("ExecutionContext not initialized.")
        return _CURRENT_CONTEXT.link

    def __getattr__(self, name):
        if _CURRENT_CONTEXT is None:
            raise RuntimeError("ExecutionContext not initialized.")
        return getattr(_CURRENT_CONTEXT, name)

ctx = _CtxProxy()
var = ctx.var

def init(context):
    global _CURRENT_CONTEXT
    _CURRENT_CONTEXT = context
