"""Bounded NetworkX layouts and explicit coordinate transforms for simple graphs."""
import math

import networkx as nx
import numpy as np


def graph_layout_positions(graph, operation='spring', positions=None, fixed_vertices=None,
                           vertices=None, root=0, iterations=150, seed=42,
                           angle=0, scale=1, offset=None):
    """Return all 2D coordinates without changing graph structure or input data.

    Fixed spring vertices retain their exact supplied coordinates. Transform
    means positive uniform scaling, counterclockwise rotation in degrees about
    the origin, then translation. Alignment uses the selected vertices' mean.
    Spectral coordinates are a drawing, not a graph-isomorphism certificate.
    """
    nodes = list(graph)
    if not 1 <= len(nodes) <= 128 or graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError('布局需要1..128顶点的无向简单图。')
    operations = {'spring', 'circular', 'spectral', 'tree', 'transform', 'align_horizontal', 'align_vertical'}
    if operation not in operations:
        raise ValueError('未知布局操作。')
    pos = None
    if positions is not None:
        pos = {}
        for record in positions:
            vertex, xy = record['vertex'], np.asarray(record['xy'], dtype=float)
            if vertex in pos or vertex not in graph or xy.shape != (2,) or not np.isfinite(xy).all() or np.max(np.abs(xy)) > 1e9:
                raise ValueError('坐标须为不重复的图中顶点及有限二维坐标，绝对值不超过10^9。')
            pos[vertex] = xy.copy()
        if set(pos) != set(nodes):
            raise ValueError('填写坐标时必须恰好覆盖全部顶点。')
    fixed = list(fixed_vertices or [])
    selected = nodes if vertices is None else list(vertices)
    if len(set(fixed)) != len(fixed) or any(v not in graph for v in fixed):
        raise ValueError('固定顶点须不重复且属于当前图。')
    if fixed and (operation != 'spring' or pos is None):
        raise ValueError('固定顶点仅适用于弹簧布局，并需提供全部初始坐标。')
    if operation == 'spring':
        if type(iterations) is not int or not 1 <= iterations <= 5000:
            raise ValueError('弹簧布局迭代次数须为1..5000。')
        if len(fixed) == len(nodes):
            coordinates = pos
        else:
            coordinates = nx.spring_layout(graph, pos=pos, fixed=fixed or None, seed=seed,
                                           iterations=iterations, weight=None)
        # Pin coordinates explicitly rather than accepting roundoff or rescaling.
        for vertex in fixed:
            coordinates[vertex] = pos[vertex].copy()
    elif operation == 'circular':
        coordinates = nx.circular_layout(graph)
    elif operation == 'spectral':
        coordinates = nx.spectral_layout(graph, weight=None)
    elif operation == 'tree':
        if root not in graph or not nx.is_tree(graph):
            raise ValueError('树形布局需要连通无圈的树，且根顶点属于该树。')
        coordinates = {}
        for depth, layer in enumerate(nx.bfs_layers(graph, root)):
            for i, vertex in enumerate(layer):
                coordinates[vertex] = np.array([i - (len(layer)-1)/2, -depth], dtype=float)
    else:
        if pos is None:
            raise ValueError('坐标变换和对齐需要提供全部顶点坐标。')
        coordinates = {v: xy.copy() for v, xy in pos.items()}
        if operation == 'transform':
            shift = np.asarray([0, 0] if offset is None else offset, dtype=float)
            if not math.isfinite(angle) or not math.isfinite(scale) or scale <= 0 or shift.shape != (2,) or not np.isfinite(shift).all():
                raise ValueError('旋转角、正缩放倍数及二维平移量必须有限。')
            radians = math.radians(angle)
            rotation = np.array([[math.cos(radians), -math.sin(radians)],
                                 [math.sin(radians), math.cos(radians)]])
            coordinates = {v: scale * (rotation @ xy) + shift for v, xy in coordinates.items()}
        else:
            if not selected or len(set(selected)) != len(selected) or any(v not in graph for v in selected):
                raise ValueError('对齐顶点须非空、不重复且属于当前图。')
            axis = 1 if operation == 'align_horizontal' else 0
            mean = float(np.mean([coordinates[v][axis] for v in selected]))
            for vertex in selected:
                coordinates[vertex][axis] = mean
    if any(not np.isfinite(xy).all() or np.max(np.abs(xy)) > 1e9 for xy in coordinates.values()):
        raise ValueError('结果坐标超出有限范围或绝对值超过10^9。')
    return [{'vertex':v, 'xy':np.asarray(coordinates[v], dtype=float).tolist()} for v in nodes]
