"""Compatibility import; implementation: graph_research.tools.extensions."""
from importlib import import_module
import sys
_impl = import_module("graph_research.tools.extensions")
sys.modules[__name__] = _impl
