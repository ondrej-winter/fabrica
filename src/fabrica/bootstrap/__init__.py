"""Lazy public composition-root API for Fabrica."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from fabrica.bootstrap._composition_exports import ROOT_BOOTSTRAP_EXPORT_MODULES, ROOT_BOOTSTRAP_EXPORT_NAMES

__all__ = list(ROOT_BOOTSTRAP_EXPORT_NAMES)


def __getattr__(name: str) -> Any:
    """Load public composition helpers on first access."""
    try:
        module_name = ROOT_BOOTSTRAP_EXPORT_MODULES[name]
    except KeyError as err:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from err
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
