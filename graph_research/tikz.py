"""Compatibility import; implementation: graph_research.rendering.tikz."""
from importlib import import_module
import sys
_impl = import_module("graph_research.rendering.tikz")
sys.modules[__name__] = _impl
