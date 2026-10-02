"""Mechanical Runtime Trace to Numeric IR translation."""

from importlib import import_module

__all__ = ["ConversionRefused", "translate", "translate_to_directory"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module(".translator", __name__), name)
