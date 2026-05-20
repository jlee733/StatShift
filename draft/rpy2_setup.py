"""Initialize rpy2 conversion rules for Streamlit (main thread + context manager)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

_converter: Any = None


def get_rpy2_converter() -> Any:
    """Build (once) the default + pandas conversion bundle."""
    global _converter
    if _converter is not None:
        return _converter

    from rpy2.robjects import default_converter, numpy2ri, pandas2ri

    _converter = default_converter + numpy2ri.converter + pandas2ri.converter
    return _converter


def init_rpy2_on_main_thread() -> Any:
    """
    Call once from Streamlit's main script thread before any R work.

    Sets global conversion rules and marks this thread as R's init thread.
    """
    import rpy2.rinterface_lib.embedded as embedded
    from rpy2.robjects import conversion

    if not embedded.isinitialized():
        embedded.set_init_thread()

    converter = get_rpy2_converter()
    conversion.set_conversion(converter)
    return converter


@contextmanager
def rpy2_session() -> Iterator[Any]:
    """
    Run rpy2/R code with conversion rules applied.

    Use around every block that calls into R from Streamlit reruns or worker threads.
    """
    from rpy2.robjects.conversion import localconverter

    converter = get_rpy2_converter()
    with localconverter(converter):
        yield converter
