"""Layouts, static figures, editor and TikZ export."""
from importlib import import_module
_EXPORTS = {'HyperGraphPlot':('plotting','HyperGraphPlot'),
            'write_editor':('editor','write_editor'),
            'graph_to_tikz':('tikz','graph_to_tikz'),
            'hypergraph_to_tikz':('tikz','hypergraph_to_tikz')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS: raise AttributeError(name)
    module,attribute = _EXPORTS[name]
    value = getattr(import_module(__name__+'.'+module),attribute)
    globals()[name] = value
    return value
