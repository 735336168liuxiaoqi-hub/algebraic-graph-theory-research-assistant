"""Shared layouts and interpolating Bezier geometry; no model dependency."""
import math
import numpy as np
import networkx as nx

COLORS = ("black", "#d62728", "#228833", "#2255cc", "#0099aa",
          "#aa33aa", "#b8860b", "#dd6699", "#885533")

def vertex_positions(h, pos=None, *, layout="spring", seed=42, iterations=150):
    """Layout the incidence graph, then hide its hyperedge nodes."""
    nodes = h.vertices()
    if pos is not None:
        if set(pos) != set(nodes):
            raise ValueError("pos must provide exactly one position per vertex")
        result = {v: np.asarray(pos[v], dtype=float) for v in nodes}
        if any(p.shape != (2,) or not np.isfinite(p).all() for p in result.values()):
            raise ValueError("Vertex positions must be finite 2D coordinates")
        if len({tuple(p) for p in result.values()}) != len(nodes):
            raise ValueError("Distinct vertices must have distinct positions")
        return result
    if layout not in ("spring", "circular"):
        raise ValueError("layout must be spring or circular")
    if not nodes:
        return {}
    if layout == "circular":
        return {v: np.array([math.cos(2*math.pi*i/len(nodes)),
                             math.sin(2*math.pi*i/len(nodes))]) for i, v in enumerate(nodes)}
    if type(iterations) is not int or not 1 <= iterations <= 5000:
        raise ValueError("iterations must be an integer in [1,5000]")
    graph = h.incidence_graph()
    result, cursor = {}, 0.0
    # Disconnected spring layouts push isolates far away and squash the main
    # drawing. Lay out each component independently, then pack horizontally.
    for component in sorted(nx.connected_components(graph), key=len, reverse=True):
        members = [v for v in nodes if ("v",v) in component]
        subgraph = graph.subgraph([node for node in graph if node in component])
        coordinates = nx.spring_layout(subgraph, seed=seed, iterations=iterations)
        xy = np.array([coordinates[("v",v)] for v in members])
        xy -= xy.mean(axis=0)
        span = np.ptp(xy,axis=0).max()
        if span:
            xy *= math.sqrt(len(members))/span
        left, right = xy[:,0].min(), xy[:,0].max()
        xy[:,0] += cursor-left
        cursor += max(right-left,.5)+1.0
        result.update(zip(members,xy))
    xy = np.array([result[v] for v in nodes])
    center = (xy.max(axis=0)+xy.min(axis=0))/2
    return {v: p-center for v,p in result.items()}

def hyperedge_path(points, *, tension=.5, continuity=.5, bias=0):
    """Cubic Bezier representation of a closed interpolating TCB spline.

    Every member is an exact segment endpoint. Binary edges are straight.
    Collinear higher edges get a small perpendicular bend to keep a visible
    loop; the supplied vertex positions are never moved.
    """
    from matplotlib.path import Path as MplPath
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 2 or not np.isfinite(points).all():
        raise ValueError("At least two finite 2D points required")
    if any(not math.isfinite(float(v)) or not -1 <= v <= 1 for v in (tension, continuity, bias)):
        raise ValueError("TCB parameters must lie in [-1,1]")
    if len(points) == 2:
        return MplPath(points, [MplPath.MOVETO, MplPath.LINETO])
    center = points.mean(axis=0)
    points = points[np.argsort(np.arctan2(points[:, 1]-center[1], points[:, 0]-center[0]), kind="stable")]
    before = points-np.roll(points, 1, axis=0)
    after = np.roll(points, -1, axis=0)-points
    incoming = .5*(1-tension)*((1+bias)*(1-continuity)*before + (1-bias)*(1+continuity)*after)
    outgoing = .5*(1-tension)*((1+bias)*(1+continuity)*before + (1-bias)*(1-continuity)*after)
    collinear = np.linalg.matrix_rank(points-center) < 2
    vertices, codes = [points[0]], [MplPath.MOVETO]
    for i, p in enumerate(points):
        j = (i+1) % len(points)
        c1, c2 = p+outgoing[i]/3, points[j]-incoming[j]/3
        if collinear:
            delta = points[j]-p
            bend = .12*np.array([-delta[1], delta[0]])
            c1, c2 = p+delta/3+bend, p+2*delta/3+bend
        vertices.extend([c1, c2, points[j]])
        codes.extend([MplPath.CURVE4]*3)
    vertices.append(points[0]); codes.append(MplPath.CLOSEPOLY)
    return MplPath(np.asarray(vertices), codes)
