"""Optional LangGraph experiment workflow."""
from importlib import import_module
_EXPORTS = {'NativeBackend':('backend','NativeBackend'),'build_workflow':('workflow','build_workflow')}
__all__ = list(_EXPORTS)
def __getattr__(name):
    if name not in _EXPORTS: raise AttributeError(name)
    module,attribute = _EXPORTS[name]
    value = getattr(import_module(__name__+'.'+module),attribute)
    globals()[name] = value
    return value
