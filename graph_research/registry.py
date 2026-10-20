"""Compatibility import; implementation: graph_research.tools.registry."""
from importlib import import_module
import sys
_impl = import_module("graph_research.tools.registry")
sys.modules[__name__] = _impl
