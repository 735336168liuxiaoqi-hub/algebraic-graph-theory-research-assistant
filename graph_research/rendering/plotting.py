"""Static rendering and JSON plot adapter."""
from pathlib import Path
from graph_research.graph_input.document import display_label
import math
import uuid
import numpy as np
from .geometry import COLORS,vertex_positions,hyperedge_path
from graph_research.runtime.observability import timed

class HyperGraphPlot:
    """Sage-style drawing wrapper; plot() returns a Matplotlib Figure.

    Supports pos, layout, seed, vertex_labels (bool/mapping), edge_labels,
    edge_colors (sequence or index mapping), edge_thickness, vertex_size,
    figsize, title, legend, tension, continuity, bias and an existing ax.
    It does not emulate arbitrary Sage Graphics/show options.
    """
    def __init__(self, hypergraph, options=None, **kwargs):
        self.hypergraph = hypergraph
        self.options = {**(options or {}), **kwargs}

    def plot(self, **options):
        return self._render(**{**self.options, **options})

    def _render(self, *, pos=None, layout="spring", seed=42, iterations=150,
             vertex_labels=True, edge_labels=False, edge_colors=None,
             edge_thickness=1.8, vertex_size=28, figsize=(7, 5), title=None,
             legend=False, tension=.5, continuity=.5, bias=0, ax=None,weight_labels=True, **kwargs):
        if kwargs:
            raise TypeError(f"Unsupported plot options: {', '.join(kwargs)}")
        from matplotlib.figure import Figure
        from matplotlib.patches import PathPatch
        from matplotlib.lines import Line2D
        from matplotlib.colors import to_rgba
        h = self.hypergraph
        from .fonts import label_font_families
        labels=vertex_labels if isinstance(vertex_labels,dict) else getattr(h,'vLabels',{})
        text=' '.join(str(labels.get(v,display_label(v))) for v in h.Vertices) if vertex_labels is not False else ''
        font_families=label_font_families(text+' '+str(title or ''))
        stored = getattr(h, "_pos", None)
        positions = vertex_positions(h, stored if pos is None and stored else pos,
                                     layout=layout, seed=seed, iterations=iterations)
        if not math.isfinite(edge_thickness) or edge_thickness <= 0 or not math.isfinite(vertex_size) or vertex_size <= 0:
            raise ValueError("Positive finite line width and vertex size required")
        if ax is None:
            figure = Figure(figsize=figsize, layout="constrained")
            ax = figure.add_subplot()
        else:
            figure = ax.figure
        colors, paths = [], []
        simple = all(len(edge)==2 for edge in h.Edges)
        for i, edge in enumerate(h.Edges):
            if edge_colors is None:
                color = getattr(edge, "color", "black" if simple else COLORS[i % len(COLORS)])
            elif isinstance(edge_colors, dict):
                color = edge_colors.get(i, COLORS[i % len(COLORS)])
            else:
                if len(edge_colors) != h.size():
                    raise ValueError("edge_colors must have one color per hyperedge")
                color = edge_colors[i]
            to_rgba(color)
            path = hyperedge_path([positions[v] for v in edge], tension=tension, continuity=continuity, bias=bias)
            patch = PathPatch(path, fill=False, edgecolor=color, linewidth=edge_thickness,
                              linestyle="solid" if simple else ("solid", "dashed", "dotted")[(i//len(COLORS)) % 3], zorder=2)
            patch.set_gid(f"hyperedge-{i}"); ax.add_patch(patch)
            paths.append(path); colors.append(color)
            if edge_labels:
                # Midpoint of the first cubic segment, away from its vertices.
                p = path.vertices
                point = (p[0]+3*p[1]+3*p[2]+p[3])/8 if len(edge)>2 else (p[0]+p[1])/2
                ax.annotate(f"e{i}", point, xytext=(3, 4), textcoords="offset points",
                            color=color, fontsize=9, fontfamily=font_families, zorder=5,
                            bbox={"facecolor":"white", "edgecolor":"none", "alpha":.8, "pad":1})
            if weight_labels and np.any(h.weights!=1):
                from .presentation import weight_text,midpoint
                ax.annotate(weight_text(float(h.weights[i])),midpoint(path),xytext=(3,-12 if edge_labels else 4),textcoords='offset points',fontsize=9,fontfamily=font_families,zorder=5)
        if positions:
            xy = np.array([positions[v] for v in h.Vertices])
            ax.scatter(xy[:,0], xy[:,1], s=vertex_size, c="black", zorder=6)
            if vertex_labels is not False:
                labels = vertex_labels if isinstance(vertex_labels, dict) else getattr(h, "vLabels", {})
                for v in h.Vertices:
                    neighbors = list(dict.fromkeys(u for edge in h.Edges if v in edge for u in edge if u!=v))
                    if neighbors:
                        rays = np.array([positions[u]-positions[v] for u in neighbors])
                        angles = np.sort(np.arctan2(rays[:,1],rays[:,0]))
                        ends = np.append(angles[1:],angles[0]+2*math.pi)
                        gap = int(np.argmax(ends-angles))
                        direction = (angles[gap]+ends[gap])/2
                        dx,dy = math.cos(direction),math.sin(direction)
                    else:
                        dx,dy = 1,0
                    ax.annotate(str(labels.get(v,display_label(v))), positions[v], xytext=(8*dx,8*dy),
                                ha="left" if dx>.2 else "right" if dx<-.2 else "center",
                                va="bottom" if dy>.2 else "top" if dy<-.2 else "center",
                                textcoords="offset points", fontsize=10, fontfamily=font_families, zorder=7,
                                bbox={"facecolor":"white", "edgecolor":"none", "alpha":.75, "pad":.3})
        if legend and h.size():
            legend_families=label_font_families(' '.join(map(str,h.Vertices)))
            ax.legend(handles=[Line2D([],[],color=color,label=f"e{i}: {{{', '.join(map(str, edge))}}}")
                               for i,(edge,color) in enumerate(zip(h.Edges,colors))],
                      loc="upper left", bbox_to_anchor=(1,1), frameon=False, fontsize=9,
                      prop={'family':legend_families,'size':9} if legend_families else None)
        if title:
            ax.set_title(title,fontfamily=font_families)
        ax.set_aspect("equal"); ax.autoscale_view(); ax.margins(.18); ax.axis("off")
        # Structured metadata also allows geometric verification and later editing.
        figure.hypergraph_positions = {v: p.copy() for v,p in positions.items()}
        figure.hypergraph_paths = paths
        return figure

    @timed('artifact_export')
    def save(self, path, *, dpi=180, **options):
        from graph_research.runtime.storage import staged_file
        overwrite=options.pop('overwrite',False)
        path = Path(path)
        if path.suffix.lower() not in (".png", ".svg", ".pdf"):
            raise ValueError("Plot output must be PNG, SVG or PDF")
        figure = self.plot(**options)
        with staged_file(path,overwrite=overwrite) as temporary:
            figure.savefig(temporary, dpi=dpi, bbox_inches="tight", facecolor="white")
        return path.resolve()

    def show(self, **options):
        # Register the artists with a pyplot figure only on explicit GUI display.
        import matplotlib.pyplot as plt
        figure, ax = plt.subplots()
        self.plot(ax=ax, **options)
        plt.show()
        return figure

def hypergraph_plot_tool(edges, vertices=None, layout="spring", seed=42,
                         edge_labels=True, legend=True, positions=None,graph_document=None):
    """Save plots into a generated task-owned directory, never a model-chosen path."""
    if graph_document is not None:
        from .presentation import presentation_document,save_document_images
        graph=presentation_document(edges,vertices,positions,graph_document)
        graph=graph.with_updates(style={'edge_labels':edge_labels,**graph.to_dict().get('style',{})})
        return save_document_images(graph,layout=layout,seed=seed,legend=legend)
    from graph_research.hypergraphs import Hypergraph
    h = Hypergraph(edges, vertices=vertices)
    if h.order() > 128 or sum(map(len, h.Edges)) > 2048:
        raise ValueError("Plot tool supports at most128 vertices and2048 incidences")
    from graph_research.runtime.storage import safe_path
    output = safe_path(Path.cwd()/"outputs"/"hypergraph-plots"/uuid.uuid4().hex)
    pos=None
    if positions is not None:
        if len({record['vertex'] for record in positions})!=len(positions):raise ValueError('顶点坐标记录重复。')
        pos={record['vertex']:record['xy'] for record in positions}
    drawing = HyperGraphPlot(h, pos=pos, layout=layout, seed=seed, edge_labels=edge_labels, legend=legend)
    figure = drawing.plot()
    output.mkdir(parents=True)
    paths = {}
    for ext in ("png", "svg"):
        path = output/f"hypergraph.{ext}"
        figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        paths[ext] = str(path.resolve())
    return {"files":paths, "order":h.order(), "size":h.size(), "uniform":h.is_uniform(),
            "positions":[{"vertex":v,"xy":xy.tolist()} for v,xy in figure.hypergraph_positions.items()],
            "edge_members":[list(e) for e in h.Edges],
            "interpretation":"Members lie ON each unfilled curve; interior vertices and unmarked crossings do not imply membership."}

def plotting_tool_definitions(object_schema):
    from graph_research.graph_input.styles import GRAPH_DOCUMENT_SCHEMA
    label = {"type":["integer","string"]}
    return [("hypergraph_plot", "按原Sage风格绘制一致或非一致超图：不填充曲线穿过成员顶点，二元边为线段；返回PNG/SVG路径和超边成员表。",
             hypergraph_plot_tool, object_schema({
                 'graph_document':GRAPH_DOCUMENT_SCHEMA,
                 "edges":{"type":"array","maxItems":128,"items":{"type":"array","minItems":2,"maxItems":128,"items":label}},
                 "vertices":{"type":"array","maxItems":128,"items":label},
                 "positions":{"type":"array","maxItems":128,"items":object_schema({'vertex':label,'xy':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-1e9,'maximum':1e9}}},['vertex','xy'])},
                 "layout":{"enum":["spring","circular"]}, "seed":{"type":"integer","minimum":0,"maximum":4294967295},
                 "edge_labels":{"type":"boolean"}, "legend":{"type":"boolean"}}, ["edges"]))]
