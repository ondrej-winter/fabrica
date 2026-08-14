"""Lazy access to focused composition-root helpers."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from fabrica.bootstrap._composition_exports import COMPOSITION_EXPORT_MODULES, COMPOSITION_EXPORT_NAMES

__all__ = list(COMPOSITION_EXPORT_NAMES)


def __getattr__(name: str) -> Any:
    """Load composition helpers on first access."""
    try:
        module_name = COMPOSITION_EXPORT_MODULES[name]
    except KeyError as err:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from err
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
