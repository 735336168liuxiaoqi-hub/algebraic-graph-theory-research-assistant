"""Compatibility import; implementation: graph_research.algebra.linear."""
from importlib import import_module
import sys
_impl = import_module("graph_research.algebra.linear")
sys.modules[__name__] = _impl
