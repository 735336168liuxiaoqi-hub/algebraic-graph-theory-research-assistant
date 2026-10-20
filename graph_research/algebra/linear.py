"""Matrix functions use SymPy for exact arithmetic and NumPy for numeric blocks."""
import numpy as np
from graph_research._lazy import sympy as sp


def BL2Bk(sizes):
    blocks, start = [], 0
    for size in sizes:
        if type(size) is not int or size < 0: raise ValueError("Invalid block size")
        blocks.append(list(range(start, start+size))); start += size
    return blocks


def subdivide(matrix, row_blocks, col_blocks=None, bksize=True):
    a = sp.Matrix(matrix)
    rows = BL2Bk(row_blocks) if bksize else row_blocks
    columns = rows if col_blocks is None else (BL2Bk(col_blocks) if bksize else col_blocks)
    return [[a.extract(r, c) for c in columns] for r in rows]


Subdivide = subdivide


def perm_block(matrix, row_blocks, col_blocks=None):
    columns = row_blocks if col_blocks is None else col_blocks
    return sp.Matrix(matrix).extract([i for b in row_blocks for i in b], [i for b in columns for i in b])


def GenerateMatrix(equations, variables):
    return sp.linear_eq_to_matrix(equations, variables)


def symbolMatrix(m, n, name):
    return sp.Matrix(m, n, lambda i, j: sp.Symbol(f"{name}{i+1}{j+1}"))


def charmat(matrix, var=None):
    a = sp.Matrix(matrix)
    if a.rows != a.cols: raise ValueError("Square matrix required")
    return (sp.Symbol("x") if var is None else var)*sp.eye(a.rows)-a


def toeplitz_matrix(ring, column, row):
    """Legacy row argument omits the top-left entry (which comes from column)."""
    return sp.Matrix(len(column), len(row)+1, lambda i, j: column[i-j] if i >= j else row[j-i-1])


def matrix_function_Jordan(matrix, function):
    a = sp.Matrix(matrix)
    transform, jordan = a.jordan_form()
    symbol = sp.Symbol("x")
    expression = function(symbol) if callable(function) else sp.sympify(function)
    out = sp.zeros(a.rows)
    offset = 0
    for block in jordan.get_diag_blocks():
        size = block.rows; value = block[0, 0]
        for i in range(size):
            for j in range(i, size):
                out[offset+i, offset+j] = sp.diff(expression, symbol, j-i).subs(symbol, value)/sp.factorial(j-i)
        offset += size
    return sp.simplify(transform*out*transform.inv())


def Mat_Subs(matrix, substitutions, ring=None):
    return sp.Matrix(matrix).subs(substitutions, simultaneous=True)


def CoSubmatrix(matrix, rows, columns=None):
    a = sp.Matrix(matrix)
    columns = rows if columns is None else columns
    return a.extract([i for i in range(a.rows) if i not in rows],
                     [i for i in range(a.cols) if i not in columns])


def laplacian_expansion(matrix, i, minor=True, ltx=False):
    a = sp.Matrix(matrix)
    terms = [(-1)**(i+j)*a[i, j]*a.minor_submatrix(i, j).det() for j in range(a.cols)]
    return sp.latex(sp.Add(*terms, evaluate=False)) if ltx else terms


def alg_Mimor(matrix, i, j, ltx=False):
    value = (-1)**(i+j)*sp.Matrix(matrix).minor_submatrix(i, j).det()
    return sp.latex(value) if ltx else value


def el_rop1(matrix, indices, repl=False):
    out = matrix if repl else sp.Matrix(matrix)
    out.row_swap(*indices)
    return out


def el_cop1(matrix, indices, repl=False):
    out = matrix if repl else sp.Matrix(matrix)
    out.col_swap(*indices)
    return out


def solve_rational_system(matrix, rhs):
    a, b = sp.Matrix(matrix), sp.Matrix(rhs)
    solution, parameters = a.gauss_jordan_solve(b)
    return {"solution": solution, "parameters": parameters, "domain": "rational_or_symbolic"}

from .integer_systems import solve_integer_linear_system

def solve_linear_system(A,B):
    """Adapted legacy entry: structured integer solutions/conditions, not a rational solution."""
    return solve_integer_linear_system(A,B)

from .elementary import el_rop2,el_rop3,el_cop2,el_cop3,do_Actions,Op_links,do_show_ops,lst2ltx,sum_hold,split_row,split_vector,show_equtions,stdequs,Mat2PR,matrix_round,map_round
