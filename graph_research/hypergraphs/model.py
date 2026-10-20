"""Hypergraph storage/structure; spectra and presentation use explicit mixins."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp

from .spectral import HypergraphSpectralMixin
from .presentation import HypergraphPresentationMixin
from ._methods import HypergraphOperationsMixin

class edge(tuple):
    """Immutable vertex tuple with legacy edge metadata."""
    def __new__(cls,values): return tuple.__new__(cls,values)
    def __init__(self,values):
        self.vertices=list(self); self.order=len(self); self.index=-1
        self.label="e-1"; self.G=None; self._weight=1.0
    @property
    def weight(self): return self._weight if self.G is None else float(self.G.weights[self.index])
    @weight.setter
    def weight(self,value):
        if not math.isfinite(float(value)) or value<=0: raise ValueError("Positive finite edge weight required")
        self._weight=float(value)
        if self.G is not None: self.G.weights[self.index]=value
    def issuperset(self,other): return set(self).issuperset(other)
    def __sub__(self,other): return edge(v for v in self if v not in other)
    def intersection(self,other): return edge(v for v in self if v in other)
    def __and__(self,other): return self.intersection(other)
    def __add__(self,other): return edge(dict.fromkeys([*self,*other]))

class Hypergraph(HypergraphSpectralMixin, HypergraphPresentationMixin, HypergraphOperationsMixin):
    """简单超图的数据模型；结构允许非一致，张量运算另检查一致性。

    edges中每边至少两个不同的可哈希顶点，不允许重复边。vertices可显式
    保留孤立点；省略时从边成员排序推断。weights为逐边有限正权，
    vertex_degrees是独立D对角，不是邻接项的任意顶点乘权。
    模型工具对标签/规模的限制比此Python对象更窄，见运行时catalog。
    """

    def __init__(self, edges=(), vertices=None, weights=None, vertex_degrees=None, V=None):
        if V is not None:
            if vertices is not None:
                raise ValueError('Use vertices or V, not both')
            vertices = V
        if isinstance(edges, Hypergraph):
            old = edges
            vertices = old.vertices() if vertices is None else vertices
            weights = old.weights.copy() if weights is None else weights
            vertex_degrees = old.vertex_degrees.copy() if vertex_degrees is None and old.vertex_degrees is not None else vertex_degrees
            edges = old.hyperedges()
        elif isinstance(edges, nx.Graph):
            vertices = list(edges) if vertices is None else vertices
            edges = list(edges.edges())
        elif type(edges) is int:
            vertices = list(range(edges))
            edges = []
        elif isinstance(edges, np.ndarray):
            if edges.ndim != 2 or not np.isin(edges, [0, 1]).all():
                raise ValueError('Binary incidence matrix required')
            vertices = list(range(edges.shape[0]))
            edges = [[i for i in vertices if edges[i, j]] for j in range(edges.shape[1])]
        self.Edges = [edge(e) for e in edges]
        if any((len(e) < 2 or len(set(e)) != len(e) for e in self.Edges)):
            raise ValueError('Hyperedges must contain at least two distinct vertices')
        if len({frozenset(e) for e in self.Edges}) != len(self.Edges):
            raise ValueError('Repeated hyperedges are not supported')
        seen = set(itertools.chain.from_iterable(self.Edges))
        if vertices is None:
            try:
                vertices = sorted(seen)
            except TypeError:
                vertices = sorted(seen, key=repr)
        self.Vertices = list(vertices)
        if len(set(self.Vertices)) != len(self.Vertices) or not seen <= set(self.Vertices):
            raise ValueError('Invalid vertex list')
        self.weights = np.array(weights if weights is not None else np.ones(len(self.Edges)), dtype=float, copy=True)
        if self.weights.shape != (len(self.Edges),) or not np.isfinite(self.weights).all() or np.any(self.weights <= 0):
            raise ValueError('One finite positive weight per edge is required')
        self.rank = max(map(len, self.Edges), default=0)
        self.corank = min(map(len, self.Edges), default=0)
        self._index = {v: i for i, v in enumerate(self.Vertices)}
        self.vertex_degrees = None if vertex_degrees is None else np.array(vertex_degrees, dtype=float, copy=True)
        if self.vertex_degrees is not None and (self.vertex_degrees.shape != (len(self.Vertices),) or not np.isfinite(self.vertex_degrees).all() or np.any(self.vertex_degrees < 0)):
            raise ValueError('One finite nonnegative diagonal degree per vertex is required')
        self.reIndex()

    def reIndex(self):
        for i, e in enumerate(self.Edges):
            e.index = i
            e.label = f'e{i}'
            e.G = self
    edges_reindex = reIndex

    @property
    def Edge_Weigth(self):
        return self.weights

    @Edge_Weigth.setter
    def Edge_Weigth(self, value):
        a = np.asarray(value, dtype=float)
        if a.shape != (self.size(),) or not np.isfinite(a).all() or np.any(a <= 0):
            raise ValueError('Invalid edge weights')
        self.weights = a

    @property
    def Vertex_Weigth(self):
        return self.vertex_degrees

    @Vertex_Weigth.setter
    def Vertex_Weigth(self, value):
        a = np.asarray(value, dtype=float)
        if a.shape != (self.order(),) or not np.isfinite(a).all() or np.any(a < 0):
            raise ValueError('Invalid diagonal degrees')
        self.vertex_degrees = a

    def __copy__(self):
        return Hypergraph(self)

    def copy(self):
        return Hypergraph(self)

    def order(self):
        return len(self.Vertices)

    def size(self):
        return len(self.Edges)

    def vertices(self):
        return list(self.Vertices)

    def hyperedges(self):
        return list(self.Edges)

    def __iter__(self):
        return iter(self.Vertices)

    def __getitem__(self, vertices):
        return self.incidence_edges(vertices)

    def __repr__(self):
        return f'Hypergraph(order={self.order()}, size={self.size()}, rank={self.rank})'

    def incidence_edges(self, vertices):
        try:
            single = vertices in self._index
        except TypeError:
            single = False
        selected = {vertices} if single else set(vertices)
        return [e for e in self.Edges if selected <= set(e)]

    def degree(self, vertex):
        return sum((vertex in e for e in self.Edges))

    def degrees(self):
        return {v: self.degree(v) for v in self.Vertices}

    def degree_sequence(self):
        return list(self.degrees().values())

    def is_uniform(self):
        return self.rank == self.corank and bool(self.Edges)

    def uniform(self):
        if not self.is_uniform():
            raise ValueError('Operation requires a nonempty uniform hypergraph')
        return self.rank

    def incidence_matrix(self):
        """返回0/1关联阵：行按vertices()，列按输入超边顺序；可非一致。"""
        return np.asarray([[int(v in e) for e in self.Edges] for v in self.Vertices], dtype=int).reshape(self.order(), self.size())

    def incidence_graph(self):
        graph = nx.Graph()
        graph.add_nodes_from((('v', v) for v in self.Vertices), bipartite=0)
        graph.add_nodes_from((('e', i) for i in range(self.size())), bipartite=1)
        graph.add_edges_from(((('v', v), ('e', i)) for i, e in enumerate(self.Edges) for v in e))
        return graph

    def is_connected(self):
        return bool(self.Vertices) and nx.is_connected(self.incidence_graph())

    def adjacency_matrix(self):
        b = self.incidence_matrix()
        a = b @ b.T
        np.fill_diagonal(a, 0)
        return a

    def distance(self, u, v):
        return nx.shortest_path_length(self.incidence_graph(), ('v', u), ('v', v)) // 2

    def distance_matrix(self):
        if not self.is_connected():
            raise ValueError('Distance matrix requires a connected hypergraph')
        return np.array([[self.distance(u, v) for v in self.Vertices] for u in self.Vertices])

    def intersection_graph(self, sizes=None):
        graph = nx.Graph()
        graph.add_nodes_from(range(self.size()))
        allowed = None if sizes is None else {sizes} if isinstance(sizes, int) else set(sizes)
        for i, j in itertools.combinations(range(self.size()), 2):
            weight = len(set(self.Edges[i]) & set(self.Edges[j]))
            if weight and (allowed is None or weight in allowed):
                graph.add_edge(i, j, weight=weight)
        return graph
    AdjacencyTensor = HypergraphSpectralMixin.adjacency_tensor

    def spanning_subgraph(self, indices):
        return Hypergraph([self.Edges[i] for i in indices], self.Vertices, [self.weights[i] for i in indices])

    def induced_subgraph(self, vertices):
        selected = set(vertices)
        indices = [i for i, e in enumerate(self.Edges) if set(e) <= selected]
        return Hypergraph([self.Edges[i] for i in indices], list(vertices), [self.weights[i] for i in indices])

    def Relabel(self, L=None, inv=False):
        if L is None:
            mapping = {v: i for i, v in enumerate(self.Vertices)}
        elif isinstance(L, dict):
            mapping = {v: L.get(v, v) for v in self.Vertices}
        else:
            if len(L) != self.order() or set(L) != set(self.Vertices):
                raise ValueError('L must list old vertices in the new order')
            mapping = {v: i for i, v in enumerate(L)}
        if len(set(mapping.values())) != self.order():
            raise ValueError('Relabeling must be one-to-one; use merge_vertices for identifications')
        graph = Hypergraph([[mapping[v] for v in e] for e in self.Edges], vertices=[mapping[v] for v in self.Vertices], weights=self.weights, vertex_degrees=self.vertex_degrees)
        return (graph, mapping) if inv else graph

    def add_edges(self, E, replace=True):
        edges = self.hyperedges()
        weights = list(self.weights)
        known = {frozenset(e) for e in edges}
        for e in E:
            if frozenset(e) not in known:
                edges.append(tuple(e))
                weights.append(1)
                known.add(frozenset(e))
        graph = Hypergraph(edges, vertices=list(dict.fromkeys(self.Vertices + list(itertools.chain.from_iterable(edges)))), weights=weights)
        if replace:
            self.__dict__.update(graph.__dict__)
            self.reIndex()
            return self
        return graph

    def delete_edges(self, E, replace=True):
        chosen = {frozenset(self.Edges[e] if type(e) is int else e) for e in E}
        indices = [i for i, e in enumerate(self.Edges) if frozenset(e) not in chosen]
        graph = Hypergraph([self.Edges[i] for i in indices], vertices=self.Vertices, weights=[self.weights[i] for i in indices])
        if replace:
            self.__dict__.update(graph.__dict__)
            self.reIndex()
            return self
        return graph

    def delete_vertices(self, S, replace=True):
        graph = self.induced_subgraph([v for v in self.Vertices if v not in S])
        if replace:
            self.__dict__.update(graph.__dict__)
            self.reIndex()
            return self
        return graph

    def _symmetry_graph(self):
        graph = self.incidence_graph()
        for i in range(self.size()):
            graph.nodes['e', i]['color'] = ('e', float(self.weights[i]))
        for i, v in enumerate(self.Vertices):
            graph.nodes['v', v]['color'] = ('v', None if self.vertex_degrees is None else float(self.vertex_degrees[i]))
        return graph

    def automorphism_group(self, max_maps=100000):
        from graph_research.core.symmetry import AutomorphismGroup
        graph = self._symmetry_graph()
        group = AutomorphismGroup(graph, nodes=[('v', v) for v in self.Vertices], node_match=lambda a, b: a['color'] == b['color'], max_maps=max_maps, projection=lambda v: v[1])
        return group

    def orbit_subdivision(self):
        from graph_research.core.symmetry import automorphism_orbits
        graph = self._symmetry_graph()
        return [[v[1] for v in block] for block in automorphism_orbits(graph, [('v', v) for v in self.Vertices], lambda a, b: a['color'] == b['color'])]

    def all_paths(self, u, v, max_paths=10000):
        paths = []
        for path in nx.all_simple_paths(self.incidence_graph(), ('v', u), ('v', v)):
            paths.append([self.Edges[p[1]] if p[0] == 'e' else p[1] for p in path])
            if len(paths) > max_paths:
                raise RuntimeError('Hypergraph path enumeration budget exceeded')
        return paths

    def distance1(self, u, v):
        return self.distance(u, v)

    def edge_weight(self, e, X):
        return math.prod((X[self._index[v]] for v in e))

    def name(self, value=None):
        if value is not None:
            self._name = str(value)
        return getattr(self, '_name', 'Hypergraph')

    def __add__(self, other):
        from graph_research.hypergraphs.operations import Disjoint_Union
        return Disjoint_Union([self, other])

    def disjoint_union(self, other, relabel=False):
        from graph_research.hypergraphs.operations import Disjoint_Union
        return Disjoint_Union([self, other], relabel)

HyperG = Hypergraph
