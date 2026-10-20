"""Exact and numerical algebra shared by graph domains."""
from importlib import import_module
__all__ = ['linear','numeric','products','polynomials','combinatorics','recurrences','integer_systems','groups','elementary','analysis','blocks']
def __getattr__(name):
    if name not in __all__: raise AttributeError(name)
    value = import_module(__name__+'.'+name)
    globals()[name] = value
    return value
