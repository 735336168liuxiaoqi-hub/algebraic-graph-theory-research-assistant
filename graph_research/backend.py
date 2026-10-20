"""Compatibility import; implementation: graph_research.experiments.backend."""
from importlib import import_module
import sys
_impl = import_module("graph_research.experiments.backend")
sys.modules[__name__] = _impl
