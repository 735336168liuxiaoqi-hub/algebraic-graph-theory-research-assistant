"""Compatibility import; implementation: graph_research.experiments.workflow."""
from importlib import import_module
import sys
_impl = import_module("graph_research.experiments.workflow")
sys.modules[__name__] = _impl
