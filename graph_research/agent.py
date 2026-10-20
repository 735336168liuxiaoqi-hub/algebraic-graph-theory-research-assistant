"""Compatibility import; implementation: graph_research.assistant.agent."""
from importlib import import_module
import sys
_impl = import_module("graph_research.assistant.agent")
sys.modules[__name__] = _impl
