"""Exact VF2-based symmetry computations with explicit enumeration budgets."""
import networkx as nx


def _matcher(g, h, node_match=None):
    cls = nx.algorithms.isomorphism.DiGraphMatcher if g.is_directed() else nx.algorithms.isomorphism.GraphMatcher
    return cls(g,h,node_match=node_match)


def automorphism_orbits(graph, nodes=None, node_match=None):
    """Find orbits using rooted isomorphism tests, without enumerating n! maps."""
    candidates=list(graph if nodes is None else nodes)
    result=[]; remaining=set(candidates)
    for root in candidates:
        if root not in remaining: continue
        orbit=[]
        for target in candidates:
            if target not in remaining or graph.degree(root)!=graph.degree(target): continue
            left=graph.copy(); right=graph.copy()
            nx.set_node_attributes(left,False,"_research_root")
            nx.set_node_attributes(right,False,"_research_root")
            left.nodes[root]["_research_root"]=True; right.nodes[target]["_research_root"]=True
            def match(a,b):
                return a["_research_root"]==b["_research_root"] and (node_match(a,b) if node_match else True)
            if _matcher(left,right,match).is_isomorphic(): orbit.append(target)
        remaining.difference_update(orbit)
        result.append(orbit)
    return result


class AutomorphismGroup:
    """Mappings are Python dictionaries; this is not a Sage permutation group."""
    def __init__(self,graph,nodes=None,node_match=None,max_maps=100000,projection=None):
        self.graph=graph.copy(); self.nodes=list(graph if nodes is None else nodes)
        self.node_match=node_match; self.max_maps=max_maps
        self.projection=projection or (lambda v:v)

    def orbits(self): return [[self.projection(v) for v in block] for block in automorphism_orbits(self.graph,self.nodes,self.node_match)]
    def orbit(self,v): return next(block for block in self.orbits() if v in block)

    def __iter__(self):
        for count,mapping in enumerate(_matcher(self.graph,self.graph,self.node_match).isomorphisms_iter()):
            if count>=self.max_maps: raise RuntimeError("Automorphism enumeration budget exceeded")
            yield {self.projection(v):self.projection(mapping[v]) for v in self.nodes}

    def order(self): return sum(1 for _ in self)
    def gens(self): return list(self)  # all maps form a (possibly redundant) generating set
