"""Compatibility import; implementation: graph_research.algebra.polynomials."""
from importlib import import_module
import sys
_impl = import_module("graph_research.algebra.polynomials")
sys.modules[__name__] = _impl
