"""Process-wide lazy proxies for heavy third-party packages.

Importing sympy costs ~300ms and dominates tool-worker/CLI startup. Tool
registration must stay eager (the catalog is a static spec), but the symbolic
engine is only needed when a tool actually executes. Attribute access on the
proxy performs the real import once and caches it process-wide.

Rule: no module in graph_research may import sympy at module top level; use
``from graph_research._lazy import sympy as sp`` instead. isinstance checks
keep working because attribute access returns the real class.
"""
import importlib


class LazyPackage:
    """Attribute-access proxy that imports the real package on first use."""

    __slots__=('_name','_module')

    def __init__(self,name):
        object.__setattr__(self,'_name',name)
        object.__setattr__(self,'_module',None)

    def _load(self):
        module=object.__getattribute__(self,'_module')
        if module is None:
            module=importlib.import_module(object.__getattribute__(self,'_name'))
            object.__setattr__(self,'_module',module)
        return module

    def __getattr__(self,item):
        if item.startswith('__') and item.endswith('__'):raise AttributeError(item)
        return getattr(self._load(),item)

    def __repr__(self):
        return f"<LazyPackage {object.__getattribute__(self,'_name')!r}>"


sympy=LazyPackage('sympy')
