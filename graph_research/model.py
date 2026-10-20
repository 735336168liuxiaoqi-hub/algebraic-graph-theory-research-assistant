"""Compatibility import; implementation: graph_research.assistant.model."""
from importlib import import_module
import sys
_impl = import_module("graph_research.assistant.model")
sys.modules[__name__] = _impl
