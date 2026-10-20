"""Lazy public API for graph computation, rendering and optional assistants."""
from importlib import import_module
from ._version import __version__
_EXPORTS = {'Hypergraph': ('graph_research.hypergraphs', 'Hypergraph'), 'HyperG': ('graph_research.hypergraphs', 'HyperG'), 'HyperPath': ('graph_research.hypergraphs', 'HyperPath'), 'HyperCycle': ('graph_research.hypergraphs', 'HyperCycle'), 'HyperStar': ('graph_research.hypergraphs', 'HyperStar'), 'Tensor': ('graph_research.tensors', 'Tensor'), 'HyperMatrix': ('graph_research.tensors', 'HyperMatrix'), 'HyperGraphPlot': ('graph_research.rendering.plotting', 'HyperGraphPlot'), 'graphs': ('graph_research.graphs', None), 'hypergraphs': ('graph_research.hypergraphs', None), 'tensors': ('graph_research.tensors', None), 'combinatorics': ('graph_research.algebra.combinatorics', None), 'polynomials': ('graph_research.algebra.polynomials', None), 'linear_algebra': ('graph_research.algebra.linear', None), 'utilities': ('graph_research.core.utilities', None)}
_EXPORTS.update({name: ('graph_research.'+name,None) for name in ('algebra','rendering','tools','assistant','experiments','core')})
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS: raise AttributeError(name)
    module,attribute = _EXPORTS[name]
    value = import_module(module)
    if attribute is not None: value = getattr(value,attribute)
    globals()[name] = value
    return value
def __dir__(): return sorted(set(globals()) | set(__all__))
