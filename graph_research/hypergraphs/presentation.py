import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp

class HypergraphPresentationMixin:
    def graphplot(self, **options):
        """Unfilled interpolating hyperedge curves; no uniformity requirement."""
        from graph_research.rendering.plotting import HyperGraphPlot
        return HyperGraphPlot(self, **options)

    def plot(self, **options):
        """Return a Matplotlib Figure (not a Sage Graphics object)."""
        return self.graphplot(**options).plot()

    def save_plot(self, path, **options):
        return self.graphplot().save(path, **options)

    def show(self, **options):
        return self.graphplot(**options).show()

    def set_pos(self, pos):
        from graph_research.rendering.plotting import vertex_positions
        self._pos = vertex_positions(self, pos)

    def get_pos(self):
        return {v:tuple(p) for v,p in getattr(self, "_pos", {}).items()}

    def edit_layout(self, path="hypergraph-editor.html", **options):
        """Create an offline draggable layout editor; returns its HTML path."""
        from graph_research.rendering.editor import write_editor
        return write_editor(self,path,**options)

    def to_tikz(self, **options):
        """Return editable LaTeX/TikZ for the current layout."""
        from graph_research.rendering.tikz import hypergraph_to_tikz
        return hypergraph_to_tikz(self,**options)

    def save_tikz(self, path, **options):
        """Save a complete .tex document, or a tikzpicture fragment."""
        from graph_research.rendering.tikz import save_hypergraph_tikz
        return save_hypergraph_tikz(self,path,**options)

    def save_pos(self, path, **options):
        """Save typed labels, topology and coordinates as reloadable JSON."""
        from graph_research.rendering.editor import save_positions
        return save_positions(self,path,**options)

    def load_pos(self, path):
        """Load validated coordinates for this graph, without changing edges."""
        from graph_research.rendering.editor import load_positions
        return load_positions(self,path)

    @classmethod
    def from_layout(cls, path):
        """Reconstruct a hypergraph and coordinates from an editor JSON file."""
        from graph_research.rendering.editor import read_layout
        _,graph,positions = read_layout(path)
        graph.set_pos(positions)
        return graph
