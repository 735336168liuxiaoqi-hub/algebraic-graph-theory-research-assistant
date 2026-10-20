import json
import sys
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp
from graph_research.hypergraphs import Hypergraph
from graph_research.tensors.elimination import hypergraph_characteristic_polynomial, tensor_characteristic_polynomial, elimination_size, EliminationLimits


def evaluate(request):
    limits=EliminationLimits(seconds=18,max_macaulay_size=512,max_block_size=64) if request.get("symbolic_alpha") else EliminationLimits(seconds=18)
    if request["mode"]=="hypergraph":
        n=request.get("n")
        graph=Hypergraph(request["edges"],vertices=None if n is None else range(n))
        if graph.order()>32: raise ValueError("Hypergraph dimension exceeds32")
        rank=request.get("rank") or (graph.uniform() if graph.Edges else None)
        if rank is None: raise ValueError("Edgeless hypergraph requires n and rank")
        if any(len(edge)!=rank for edge in graph.Edges): raise ValueError("Specified rank does not match a uniform hypergraph")
        if request.get("estimate_only"):
            components=graph.incidence_graph()
            blocks=[[node for node in component if node[0]=="v"] for component in nx.connected_components(components)]
            estimates=[elimination_size(len(block),rank) for block in blocks if block]
            return {"estimate_only":True,"global":elimination_size(graph.order(),rank),"components":estimates,
                    "limits":{"macaulay_size":limits.max_macaulay_size,"scc_block":limits.max_block_size,"seconds":20},
                    "note":"SCC sizes and exact running time are unknown until construction; estimate is not a polynomial"}
        alpha=sp.Symbol("alpha") if request.get("symbolic_alpha") else request.get("alpha",0)
        result=hypergraph_characteristic_polynomial(graph,matrix=request.get("matrix","A"),alpha=alpha,
                    rank=request.get("rank"),weights=request.get("weights"),vertex_degrees=request.get("vertex_degrees"),
                    limits=limits,details=True)
    elif request["mode"]=="tensor":
        array=np.asarray(request["data"],dtype=object)
        if array.ndim<2 or len(set(array.shape))!=1: raise ValueError("Cubical tensor required")
        if request.get("estimate_only"): return {"estimate_only":True,**elimination_size(array.shape[0],array.ndim)}
        result=tensor_characteristic_polynomial(array,limits=limits,details=True)
    else: raise ValueError("Unknown elimination input mode")
    return result.as_dict()


def main():
    try:
        request=json.load(sys.stdin)
        result=evaluate(request)
        payload=json.dumps({"ok":True,"result":result},ensure_ascii=False,allow_nan=False)
        if len(payload)>200000: raise ValueError("Exact output exceeds200000 characters")
        print(payload)
    except Exception as exc:
        print(json.dumps({"ok":False,"error":f"{type(exc).__name__}: {exc}"}))
        return 1
    return 0


if __name__=="__main__": sys.exit(main())
