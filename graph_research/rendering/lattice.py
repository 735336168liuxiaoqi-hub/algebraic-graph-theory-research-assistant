"""Optional Matplotlib substitutes for combinatorial Sage path drawings."""
import numpy as np


def gridPath(seq,co='blue',withPoints=False):
    """0 means up and 1 means right; return a Figure, optionally (Figure,points)."""
    from matplotlib.figure import Figure
    steps=list(seq)
    if len(steps)>10000 or any(type(step) is not int or step not in (0,1) for step in steps):raise ValueError('格路由至多10000个0/1步组成。')
    points=[(0,0)]
    for step in steps:
        x,y=points[-1];points.append((x+step,y+1-step))
    figure=Figure(figsize=(6,6));axes=figure.subplots();axes.plot(*zip(*points),color=co,marker='.')
    axes.set_aspect('equal',adjustable='datalim');axes.grid(True)
    return (figure,points) if withPoints else figure


def getGridPath(x):
    """Matplotlib Figure for a zero/one grid path (legacy default red)."""
    return gridPath(x,co='red')


def lattice_path(n,C,co='blue',withPoints=False):
    """Place right steps at the zero-based indices C among n total steps."""
    indices=list(C)
    if type(n) is not int or not 0<=n<=10000 or any(type(i) is not int or not 0<=i<n for i in indices) or len(set(indices))!=len(indices):
        raise ValueError('需要有效总步数和不重复的步序号。')
    selected=set(indices)
    return gridPath([int(i in selected) for i in range(n)],co,withPoints)


def rectangle(minx,miny,maxx,maxy,co='black',f=True):
    """Return a Figure containing a filled or outline Matplotlib rectangle."""
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    values=np.array([minx,miny,maxx,maxy],dtype=float)
    if not np.isfinite(values).all() or maxx<minx or maxy<miny:raise ValueError('需要有限且有序的矩形边界。')
    figure=Figure();axes=figure.subplots();axes.add_patch(Rectangle((minx,miny),maxx-minx,maxy-miny,facecolor=co if f else 'none',edgecolor=co))
    axes.set_xlim(minx-.5,maxx+.5);axes.set_ylim(miny-.5,maxy+.5);axes.set_aspect('equal');return figure


def chess_board(matrix,cls,row_label=None,col_label=None):
    """Draw a rectangular board; cls(row,column) chooses each cell's color.

    Rows run along y and columns along x. This fixes the original mixed-up
    rectangular row/column labels rather than preserving that indexing bug.
    """
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    values=np.asarray(matrix)
    if values.ndim!=2 or not all(values.shape) or max(values.shape)>128:raise ValueError('棋盘须为非空二维矩阵，各维至多128。')
    rows,columns=values.shape
    if row_label is not None and len(row_label)!=rows:raise ValueError('行标签数量不匹配。')
    if col_label is not None and len(col_label)!=columns:raise ValueError('列标签数量不匹配。')
    figure=Figure();axes=figure.subplots()
    for i in range(rows):
        for j in range(columns):axes.add_patch(Rectangle((j,i),1,1,edgecolor='black',facecolor=cls(i,j)))
    axes.set_xlim(0,columns);axes.set_ylim(0,rows);axes.set_aspect('equal')
    axes.set_xticks(np.arange(columns)+.5,labels=col_label if col_label is not None else list(range(columns)))
    axes.set_yticks(np.arange(rows)+.5,labels=row_label if row_label is not None else list(range(rows)))
    return figure
