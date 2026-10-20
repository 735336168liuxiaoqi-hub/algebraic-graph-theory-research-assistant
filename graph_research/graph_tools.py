"""Compatibility import; implementation: graph_research.tools.graphs."""
from importlib import import_module
import sys
_impl = import_module("graph_research.tools.graphs")
sys.modules[__name__] = _impl
