"""Reproducible native-Python graph research examples; no Sage or model."""
import json
from pathlib import Path
import networkx as nx
import sympy as sp
from graph_research.registry import ToolRegistry
from graph_research import hypergraphs as hg

registry=ToolRegistry()
cases=[("theta_graph","graph_construction",{"family":"theta","lengths":[2,2,2]}),
       ("symbolic_alpha","graph_spectral_analysis",{"operation":"alpha_charpoly","kind":"path","n":3,"symbolic_alpha":True}),
       ("star_orbit_quotient","graph_symmetry",{"kind":"star","n":5}),
       ("degree_realizations","graph_enumeration",{"operation":"degree_realizations","degrees":[2,2,2,2,2,2]}),
       ("directed_triangle","directed_graph_spectrum",{"n":3,"arcs":[[0,1],[1,2],[2,0]]}),
       ("bicyclic_hypergraph","generate_hypergraph",{"family":"bicyclic_c1","lengths":[1,2,2],"k":3}),
       ("hypergraph_matching","hypergraph_structure",{"edges":[[0,1,2],[0,3,4],[0,5,6]],"operation":"matching_poly"}),
       ("hypergraph_orbit_quotient","hypergraph_quotient_spectrum",{"edges":[[0,1,2],[2,3,4],[4,5,6]],"alpha":0.3})]
results=[]
for name,tool,arguments in cases:
    result=registry.call(tool,arguments)
    results.append({"name":name,"tool":tool,"arguments":arguments,"result":result})
    print(name+": "+json.dumps(result,ensure_ascii=False))
output=Path.cwd()/"outputs/graph-calculations-v03"
output.mkdir(parents=True,exist_ok=True)
(output/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print("Saved:",output.resolve())
