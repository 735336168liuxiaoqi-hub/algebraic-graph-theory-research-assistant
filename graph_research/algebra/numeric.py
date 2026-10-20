"""Functional algebra.numeric implementation; original provenance in NOTICE.md."""
import itertools
import math
import random
from collections import defaultdict
from functools import lru_cache
import networkx as nx
import numpy as np
from graph_research._lazy import sympy as sp


def eigenpair(matrix, spe=False, order=0):
    a = np.asarray(matrix, dtype=complex if np.iscomplexobj(matrix) else float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not np.isfinite(a).all():
        raise ValueError("Expected a finite square matrix")
    if np.allclose(a, a.conj().T, rtol=0, atol=1e-12):
        values, vectors = np.linalg.eigh(a)
    else:
        values, vectors = np.linalg.eig(a)
    indices = np.argsort(values.real)[::-1]
    values, vectors = values[indices], vectors[:, indices]
    if spe:
        return values
    return values[order], vectors[:, order]


def spectral_radius(matrix, niter=2000):
    a = np.asarray(matrix, dtype=complex if np.iscomplexobj(matrix) else float)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not a.size:
        raise ValueError("Expected a nonempty square matrix")
    values, vectors = np.linalg.eig(a)
    index = int(np.argmax(np.abs(values)))
    # Prefer the positive Perron eigenvalue in a nonnegative bipartite matrix.
    if not np.iscomplexobj(a) and np.all(a >= 0):
        index = int(np.argmax(values.real))
    return float(abs(values[index])), np.real_if_close(vectors[:, index])

__all__ = ['eigenpair', 'spectral_radius']
