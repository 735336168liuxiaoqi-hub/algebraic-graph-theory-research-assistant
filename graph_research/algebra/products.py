"""Functional algebra.products implementation; original provenance in NOTICE.md."""
import itertools
import math
import numbers
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def _partition_indices(blocks, size):
    """Validate before converting; JSON integer-valued floats are legal indices."""
    try:rows=[list(block) for block in blocks]
    except TypeError:raise ValueError('分块必须是索引列表的列表。') from None
    result=[]
    for row in rows:
        if not row:raise ValueError('每个分块至少需要一个索引。')
        values=[]
        for value in row:
            if isinstance(value,(bool,np.bool_)) or not isinstance(value,numbers.Real):
                raise ValueError('分块索引必须是整数，例如0、1或1.0，不能使用布尔值或文本。')
            if not isinstance(value,numbers.Integral) and (not math.isfinite(value) or value!=math.floor(value)):
                raise ValueError('分块索引必须是有限整数，不能含小数部分、NaN或无穷大。')
            if not 0<=value<size:raise ValueError(f'分块索引超出范围，应在0到{size-1}之间。')
            values.append(int(value))
        result.append(values)
    if sorted(itertools.chain.from_iterable(result))!=list(range(size)):
        raise ValueError('分块必须恰好覆盖所有行列索引，不能重复或遗漏。')
    return result


def Quotient_Matrix(a, Bk, sym=False, **kwargs):
    a = np.asarray(a)
    if a.ndim != 2 or a.shape[0] != a.shape[1]:
        raise ValueError("Expected a square matrix and nonempty blocks")
    blocks = _partition_indices(Bk,a.shape[0])
    q = np.array([[a[np.ix_(b, c)].sum()/len(b) for c in blocks] for b in blocks])
    if sym:
        sizes = np.sqrt([len(b) for b in blocks])
        q = sizes[:, None]*q/sizes[None, :]
    return q


def Kronecker_Sum(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return np.kron(a, np.eye(len(b)))+np.kron(np.eye(len(a)), b)


def columnwise_khatri_rao(a,b):
    a,b=np.asarray(a),np.asarray(b)
    if a.shape[1]!=b.shape[1]: raise ValueError("Same number of columns required")
    return np.column_stack([np.kron(a[:,i],b[:,i]) for i in range(a.shape[1])])


def _blocks(matrix,partition):
    a=np.asarray(matrix)
    rows,columns=([a.shape[0]],[a.shape[1]]) if partition is None else partition
    if any(type(n) is not int or n<1 for n in [*rows,*columns]) or sum(rows)!=a.shape[0] or sum(columns)!=a.shape[1]:
        raise ValueError("Block sizes must partition matrix rows and columns")
    rs=np.cumsum([0]+list(rows)); cs=np.cumsum([0]+list(columns))
    return [[a[rs[i]:rs[i+1],cs[j]:cs[j+1]] for j in range(len(columns))] for i in range(len(rows))]


def Khatri_Rao_Product(a,b,blocks_a=None,blocks_b=None):
    """Legacy blockwise Kronecker product; unpartitioned inputs give kron(a,b)."""
    left,right=_blocks(a,blocks_a),_blocks(b,blocks_b)
    if len(left)!=len(right) or len(left[0])!=len(right[0]): raise ValueError("Same block-grid dimensions required")
    return np.block([[np.kron(x,y) for x,y in zip(row_a,row_b)] for row_a,row_b in zip(left,right)])


def Partitioned_tensor_product(Mp,*args,blocks_a=None,blocks_b=None):
    matrices=Mp if isinstance(Mp,list) and len(Mp)==2 and all(np.ndim(m)==2 for m in Mp) else [Mp,*args]
    if len(matrices)!=2: raise ValueError("Exactly two partitioned matrices required")
    return Khatri_Rao_Product(*matrices,blocks_a,blocks_b)


def Tracy_Singh_Product(a,b,blocks_a=None,blocks_b=None):
    left,right=_blocks(a,blocks_a),_blocks(b,blocks_b)
    return np.block([[np.kron(left[i][j],right[u][v]) for j in range(len(left[0])) for v in range(len(right[0]))]
                     for i in range(len(left)) for u in range(len(right))])


def CoSubmatrix(a,rows,columns=None):
    from graph_research.algebra.linear import CoSubmatrix as complement
    return complement(a,rows,columns)

__all__ = ['Quotient_Matrix', 'Kronecker_Sum', 'columnwise_khatri_rao', 'Khatri_Rao_Product', 'Partitioned_tensor_product', 'Tracy_Singh_Product', 'CoSubmatrix']
