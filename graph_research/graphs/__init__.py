"""Public functional API; compatibility names remain available."""
from graph_research.algebra.numeric import eigenpair, spectral_radius
from graph_research.algebra.products import CoSubmatrix, Khatri_Rao_Product, Kronecker_Sum, Partitioned_tensor_product, Quotient_Matrix, Tracy_Singh_Product, columnwise_khatri_rao
from graph_research.graphs.construction import Generalized_Theta, HammingGraph, RandBipartite, RandomCactusGraph, RandomKCyclicGraph, Random_Unicyclic_Graph, caterpillar, fan_graph, genreg, make_graph, rand_cactus_graph, random_oriente, rose_graph, theta_graph
from graph_research.graphs.enumeration import All_Paths, Count_Subgraph, Find_all_hamiltonian_cycles, Find_hamiltonian_cycle, Graphs_WithDegreeSequence, findCycles, findDiCycles, get_appand_paths, path_tree
from graph_research.graphs.matrices import ABC_matrix, Hermitian_Adjacency_Matrix, Weighted_Adjancency_Matrix, alpha_matrix, degree_matrix, distLap, distance_matrix, exact_graph_matrix, get_Matrix, hermitian_adjacency_matrix, is_transmission_regular, normalized_laplace_matrix, seidel_matrix, signless_laplacian_matrix
from graph_research.graphs.operations import Add_Edges, Add_cycles, Add_path, Blowup, Delete_Edges, Delete_Vertices, Graph_Power, HJQM, H_join, K_subdivide_graph, Rotate_Edges, add_innerPaths, add_paths, add_stars, coalescence_graphs, corona_graphs, join_graphs, linkGraph, part_join, rooted_product, seidel_switching, sew_graphs, union_graphs
from graph_research.graphs.polynomials import Energy_Diff, abs_polynomial, absch_addclaws, abscharpoly, abscharpoly_path, abscharpoly_subdivide_edge, abspm, charpolys_for_graph, exact_characteristic_polynomial, gen_poly, gen_poly1, is_quasiorder_comparable, rev_polynomial, reversed_polynomial
from graph_research.graphs.spectral import Energy, H_Spectra_Radius, Spectral_Radius, Spectral_Radius_digraph, Spectral_decomposition, angle, eigenpairs, estrada_index, findCospe, graph_spectrum, groupbyinv, inertias_of_graph, is_WF, perron_order, signature, sortGraphbyInvariant, sort_vertice_by_perron_vector, spectral_projectors, sum_connectivity
from graph_research.graphs.symmetry import Quo_Mat, automorphism_group, distance_partition, equitable_quotient, is_biregular_bipartite, orbit_subdivision
from graph_research.graphs.basic import BaseGraph,Relabel,sorted_label,generalized_line_graph,subdivide_edges
from importlib import import_module
_LAZY = {'to_tikz': ('graph_research.rendering.tikz', 'graph_to_tikz'), 'save_tikz': ('graph_research.rendering.tikz', 'save_graph_tikz')}
def __getattr__(name):
    if name not in _LAZY: raise AttributeError(name)
    module,attribute = _LAZY[name]
    value = getattr(import_module(module),attribute)
    globals()[name] = value
    return value
__all__ = ['BaseGraph','Relabel','sorted_label','generalized_line_graph','subdivide_edges','ABC_matrix', 'Add_Edges', 'Add_cycles', 'Add_path', 'All_Paths', 'Blowup', 'CoSubmatrix', 'Count_Subgraph', 'Delete_Edges', 'Delete_Vertices', 'Energy', 'Energy_Diff', 'Find_all_hamiltonian_cycles', 'Find_hamiltonian_cycle', 'Generalized_Theta', 'Graph_Power', 'Graphs_WithDegreeSequence', 'HJQM', 'H_Spectra_Radius', 'H_join', 'HammingGraph', 'Hermitian_Adjacency_Matrix', 'K_subdivide_graph', 'Khatri_Rao_Product', 'Kronecker_Sum', 'Partitioned_tensor_product', 'Quo_Mat', 'Quotient_Matrix', 'RandBipartite', 'RandomCactusGraph', 'RandomKCyclicGraph', 'Random_Unicyclic_Graph', 'Rotate_Edges', 'Spectral_Radius', 'Spectral_Radius_digraph', 'Spectral_decomposition', 'Tracy_Singh_Product', 'Weighted_Adjancency_Matrix', 'abs_polynomial', 'absch_addclaws', 'abscharpoly', 'abscharpoly_path', 'abscharpoly_subdivide_edge', 'abspm', 'add_innerPaths', 'add_paths', 'add_stars', 'alpha_matrix', 'angle', 'automorphism_group', 'caterpillar', 'charpolys_for_graph', 'coalescence_graphs', 'columnwise_khatri_rao', 'corona_graphs', 'degree_matrix', 'distLap', 'distance_matrix', 'distance_partition', 'eigenpair', 'eigenpairs', 'equitable_quotient', 'estrada_index', 'exact_characteristic_polynomial', 'exact_graph_matrix', 'fan_graph', 'findCospe', 'findCycles', 'findDiCycles', 'gen_poly', 'gen_poly1', 'genreg', 'get_Matrix', 'get_appand_paths', 'graph_spectrum', 'groupbyinv', 'hermitian_adjacency_matrix', 'inertias_of_graph', 'is_WF', 'is_biregular_bipartite', 'is_quasiorder_comparable', 'is_transmission_regular', 'join_graphs', 'linkGraph', 'make_graph', 'normalized_laplace_matrix', 'orbit_subdivision', 'part_join', 'path_tree', 'perron_order', 'rand_cactus_graph', 'random_oriente', 'rev_polynomial', 'reversed_polynomial', 'rooted_product', 'rose_graph', 'save_tikz', 'seidel_matrix', 'seidel_switching', 'sew_graphs', 'signature', 'signless_laplacian_matrix', 'sortGraphbyInvariant', 'sort_vertice_by_perron_vector', 'spectral_projectors', 'spectral_radius', 'sum_connectivity', 'theta_graph', 'to_tikz', 'union_graphs']
def __dir__(): return sorted(set(globals()) | set(__all__))

from graph_research.graphs.adapters import set_edge_weight,weight_edges,complex_weight,edge2graph,replace_edges_by_graph,PartProduct,pick_vertices,list2dict,Index,Cycle,mygraphmul,mygraphsub,random_symmetric_matrix,AMdb
from graph_research.algebra.groups import cayley_graph
__all__ += ['set_edge_weight','weight_edges','complex_weight','edge2graph','replace_edges_by_graph','PartProduct','pick_vertices','list2dict','Index','Cycle','mygraphmul','mygraphsub','random_symmetric_matrix','AMdb','cayley_graph']

from graph_research.graphs.adapters import checksign1,polynomials_for_addstarsgraph
__all__ += ['checksign1','polynomials_for_addstarsgraph']
