"""JSON contracts and controlled computational adapters."""
from importlib import import_module
__all__ = ['Tool','ToolRegistry']
def __getattr__(name):
    if name not in __all__: raise AttributeError(name)
    value = getattr(import_module(__name__+'.registry'),name)
    globals()[name] = value
    return value
