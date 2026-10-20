"""Compatibility import; implementation: graph_research.tensors.elimination."""
from importlib import import_module
import sys
_impl = import_module("graph_research.tensors.elimination")
sys.modules[__name__] = _impl
