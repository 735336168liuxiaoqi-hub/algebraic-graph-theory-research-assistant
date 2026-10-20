"""Compatibility import; implementation: graph_research.rendering.plotting."""
from importlib import import_module
import sys
_impl = import_module("graph_research.rendering.plotting")
sys.modules[__name__] = _impl
