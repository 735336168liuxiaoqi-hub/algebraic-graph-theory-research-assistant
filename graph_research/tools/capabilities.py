"""Inspect optional package presence without importing visualization SDKs."""
from importlib.util import find_spec

VISUAL_TOOLS=frozenset({'hypergraph_plot','hypergraph_tikz','graph_tikz','hypergraph_schematic','combinatorial_plot','graph_layout'})


def tool_availability(name):
    required=['matplotlib'] if name in VISUAL_TOOLS else []
    missing=[package for package in required if find_spec(package) is None]
    return {'available':not missing,'missing_requirements':missing,
            'install_extra':'visual' if required else None}
