"""Audited Numeric IR to unchanged frozen V2 operation adapter."""

from importlib import import_module

__all__ = ["AdapterRefused", "adapt", "adapt_to_directory"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module(".adapter", __name__), name)
