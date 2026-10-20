"""Sage-style hyperedge curves with native Python only."""
from pathlib import Path
from matplotlib.figure import Figure
from graph_research import Hypergraph, HyperPath


def main():
    output = Path(__file__).resolve().parents[1]/"outputs"/"hypergraph-plot-v05"
    output.mkdir(parents=True, exist_ok=True)
    path = HyperPath(3,3)
    path_pos = {0:(-3,0),1:(-1,0),2:(1,0),3:(3,0),4:(-2,1),5:(0,-1),6:(2,1)}
    mixed = Hypergraph([[0,1,2],[2,3],[3,4,5,6]],vertices=list(range(8)))
    mixed_pos = {0:(-2,0),1:(-1,1),2:(0,0),3:(1,0),4:(2,1),5:(3,0),6:(2,-1),7:(0,1.7)}
    interior = Hypergraph([[0,1,2]],vertices=[0,1,2,3])
    interior_pos = {0:(-1,-.6),1:(1,-.6),2:(0,1),3:(0,0)}
    gallery = Figure(figsize=(14,4.4), layout="constrained")
    examples = [(path,path_pos,"3-uniform loose path"),
                (mixed,mixed_pos,"Nonuniform: edge sizes 3, 2, 4"),
                (interior,interior_pos,"Only vertices ON the curve are members")]
    for index,(h,pos,title) in enumerate(examples,1):
        h.plot(ax=gallery.add_subplot(1,3,index),pos=pos,edge_labels=True,title=title)
    for ext in ("png","svg","pdf"):
        gallery.savefig(output/f"gallery.{ext}",dpi=180,bbox_inches="tight",facecolor="white")
    mixed.save_plot(output/"nonuniform.png",pos=mixed_pos,edge_labels=True,legend=True,
                    title="Nonuniform hypergraph: interpolating curves")
    mixed.save_plot(output/"nonuniform.svg",pos=mixed_pos,edge_labels=True,legend=True)
    mixed.save_plot(output/"automatic.png",edge_labels=True,legend=True,
                    title="Automatic incidence-graph layout")
    print(output)


if __name__ == '__main__':
    main()
