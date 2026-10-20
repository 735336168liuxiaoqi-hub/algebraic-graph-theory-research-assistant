"""Compatibility import; implementation: graph_research.core.utilities."""
from importlib import import_module
import sys
_impl = import_module("graph_research.core.utilities")
sys.modules[__name__] = _impl
