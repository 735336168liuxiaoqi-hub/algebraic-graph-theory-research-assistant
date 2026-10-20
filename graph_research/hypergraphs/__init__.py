"""Public functional API; compatibility names remain available."""
from graph_research.hypergraphs.families import Bicyclic_C1, Bicyclic_C1s, Bicyclic_C2, Bicyclic_C2s, Bicyclic_C3, CompleteHyperG, EStarLike, HyperCycle, HyperPath, HyperStar, VStarLike
from graph_research.hypergraphs.model import HyperG, Hypergraph, edge
from graph_research.hypergraphs.operations import Add_innerPath, Add_innerPaths, BlowSomeEdges, Blow_Up, Coalescence_Hypergraphs, CyclomaticNumber, Disjoint_Union, Index, IsIsomorphic, Rooted_Product, TotalGraph, WeightedLineGraph, add_path, add_paths, append_edges, blowup_edge, blowup_vertex, cartesian_product_H, induced_subgraph, merge_vertices, spanning_subgraph, split_vertex, subdivide_edge, vertice_releasing
from graph_research.hypergraphs.quotients import OrbitQuotient, Quotient_Graph, edge_representative_quotient
from graph_research.hypergraphs.spectral import AdjacencyTensor, Associated_Weight_Bipartite_Graph, Matching_Polynomial, WIe, WeightIncidenceMatrix, adjacency_tensor, alpha_spectral_radius, alpha_tensor, laplacian_tensor, signless_laplacian_tensor
from graph_research.tensors.elimination import charpoly_H, charpoly_system, comp_charpoly
from importlib import import_module
_LAZY = {'HyperGraphPlot': ('graph_research.rendering.plotting', 'HyperGraphPlot')}
def __getattr__(name):
    if name not in _LAZY: raise AttributeError(name)
    module,attribute = _LAZY[name]
    value = getattr(import_module(module),attribute)
    globals()[name] = value
    return value
__all__ = ['Add_innerPath', 'Add_innerPaths', 'AdjacencyTensor', 'Associated_Weight_Bipartite_Graph', 'Bicyclic_C1', 'Bicyclic_C1s', 'Bicyclic_C2', 'Bicyclic_C2s', 'Bicyclic_C3', 'BlowSomeEdges', 'Blow_Up', 'Coalescence_Hypergraphs', 'CompleteHyperG', 'CyclomaticNumber', 'Disjoint_Union', 'EStarLike', 'HyperCycle', 'HyperG', 'HyperGraphPlot', 'HyperPath', 'HyperStar', 'Hypergraph', 'Index', 'IsIsomorphic', 'Matching_Polynomial', 'OrbitQuotient', 'Quotient_Graph', 'Rooted_Product', 'TotalGraph', 'VStarLike', 'WIe', 'WeightIncidenceMatrix', 'WeightedLineGraph', 'add_path', 'add_paths', 'adjacency_tensor', 'alpha_spectral_radius', 'alpha_tensor', 'append_edges', 'blowup_edge', 'blowup_vertex', 'cartesian_product_H', 'charpoly_H', 'charpoly_system', 'comp_charpoly', 'edge', 'edge_representative_quotient', 'induced_subgraph', 'laplacian_tensor', 'merge_vertices', 'signless_laplacian_tensor', 'spanning_subgraph', 'split_vertex', 'subdivide_edge', 'vertice_releasing']
def __dir__(): return sorted(set(globals()) | set(__all__))

from graph_research.hypergraphs.research_families import Gee,Gev,Gvv,GWG,Ca,Cva
__all__ += ['Gee','Gev','Gvv','GWG','Ca','Cva']

from graph_research.hypergraphs.attachments import add_star,add_stars
__all__ += ['add_star','add_stars']
