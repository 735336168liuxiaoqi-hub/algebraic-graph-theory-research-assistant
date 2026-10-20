"""Compatibility import; implementation: graph_research.core.symmetry."""
from importlib import import_module
import sys
_impl = import_module("graph_research.core.symmetry")
sys.modules[__name__] = _impl
