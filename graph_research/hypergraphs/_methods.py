"""Stable method signatures forwarding to the operations layer."""
class HypergraphOperationsMixin:
    def Index(self, e):
        """Compatibility method; see hypergraphs.operations.Index."""
        from graph_research.hypergraphs.operations import Index as _operation
        return _operation(self, e)

    def append_edges(self):
        """Compatibility method; see hypergraphs.operations.append_edges."""
        from graph_research.hypergraphs.operations import append_edges as _operation
        return _operation(self)

    def add_path(self, v, s, rank=0, copy=True):
        """Compatibility method; see hypergraphs.operations.add_path."""
        from graph_research.hypergraphs.operations import add_path as _operation
        return _operation(self, v, s, rank, copy)

    def add_paths(self, D, rank=0, copy=True):
        """Compatibility method; see hypergraphs.operations.add_paths."""
        from graph_research.hypergraphs.operations import add_paths as _operation
        return _operation(self, D, rank, copy)

    def merge_vertices(self, VGs, relabel=False, nv='w_'):
        """Compatibility method; see hypergraphs.operations.merge_vertices."""
        from graph_research.hypergraphs.operations import merge_vertices as _operation
        return _operation(self, VGs, relabel, nv)

    def Add_innerPath(self, VLP, l, k=None, relabel=False, nv='w'):
        """Compatibility method; see hypergraphs.operations.Add_innerPath."""
        from graph_research.hypergraphs.operations import Add_innerPath as _operation
        return _operation(self, VLP, l, k, relabel, nv)

    def Add_innerPaths(self, D, relabel=False, nv='w'):
        """Compatibility method; see hypergraphs.operations.Add_innerPaths."""
        from graph_research.hypergraphs.operations import Add_innerPaths as _operation
        return _operation(self, D, relabel, nv)

    def blowup_edge(self, k):
        """Compatibility method; see hypergraphs.operations.blowup_edge."""
        from graph_research.hypergraphs.operations import blowup_edge as _operation
        return _operation(self, k)

    def BlowSomeEdges(self, blowedges):
        """Compatibility method; see hypergraphs.operations.BlowSomeEdges."""
        from graph_research.hypergraphs.operations import BlowSomeEdges as _operation
        return _operation(self, blowedges)

    def blowup_vertex(self, d):
        """Compatibility method; see hypergraphs.operations.blowup_vertex."""
        from graph_research.hypergraphs.operations import blowup_vertex as _operation
        return _operation(self, d)

    def Blow_Up(self, VS, relabel=False):
        """Compatibility method; see hypergraphs.operations.Blow_Up."""
        from graph_research.hypergraphs.operations import Blow_Up as _operation
        return _operation(self, VS, relabel)

    def Rooted_Product(self, DvH, relabel=True):
        """Compatibility method; see hypergraphs.operations.Rooted_Product."""
        from graph_research.hypergraphs.operations import Rooted_Product as _operation
        return _operation(self, DvH, relabel)

    def subdivide_edge(self, e, k):
        """Compatibility method; see hypergraphs.operations.subdivide_edge."""
        from graph_research.hypergraphs.operations import subdivide_edge as _operation
        return _operation(self, e, k)

    def vertice_releasing(self, i, L):
        """Compatibility method; see hypergraphs.operations.vertice_releasing."""
        from graph_research.hypergraphs.operations import vertice_releasing as _operation
        return _operation(self, i, L)

    def split_vertex(self, v, n):
        """Compatibility method; see hypergraphs.operations.split_vertex."""
        from graph_research.hypergraphs.operations import split_vertex as _operation
        return _operation(self, v, n)

    def add_star(self,R,s):
        """Attach s edges sharing R, preserving edge weights and input graph."""
        from .attachments import add_star
        return add_star(self,R,s)

    def add_stars(self,rootsk):
        """Attach multiple shared-root stars on an independent copy."""
        from .attachments import add_stars
        return add_stars(self,rootsk)
