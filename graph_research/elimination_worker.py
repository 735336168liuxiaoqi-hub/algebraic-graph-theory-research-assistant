"""Compatibility import; implementation: graph_research.tools.elimination_worker."""
from importlib import import_module
import sys
_impl = import_module("graph_research.tools.elimination_worker")
if __name__ == "__main__": raise SystemExit(_impl.main())
sys.modules[__name__] = _impl
