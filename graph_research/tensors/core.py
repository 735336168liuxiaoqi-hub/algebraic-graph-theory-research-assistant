"""Dense tensor operations in NumPy; no Sage objects or pickle persistence."""
import itertools
import math
import numpy as np


def _array(value):
    return value.array if isinstance(value, Tensor) else np.asarray(value)


class Tensor:
    __array_priority__ = 1000

    def __init__(self, input_data=None, shape=None, symmetric=None, info=None):
        self.array = np.zeros(shape, dtype=float) if input_data is None else np.array(input_data, copy=True)
        if shape is not None:
            self.array = self.array.reshape(shape)
        self.shape = self.array.shape
        self.rank = self.array.ndim
        self.symmetric = symmetric
        self.info = info

    def __array__(self, dtype=None, copy=None):
        return np.array(self.array, dtype=dtype, copy=True) if copy else np.asarray(self.array, dtype=dtype)

    def size(self):
        return self.array.size

    def transpose(self, args=None):
        return Tensor(self.array.transpose(args))

    def reshape(self, shape):
        return Tensor(self.array.reshape(shape))

    def is_cubical_tensor(self):
        return bool(self.shape) and len(set(self.shape)) == 1

    def to_dict(self):
        return {index: self.array[index].item() for index in np.ndindex(self.shape) if self.array[index] != 0}

    def mean(self, axis=None):
        return self.array.mean(axis=axis)

    def tensordot(self, other, axes=None):
        """Legacy Sage method performed matmul. Explicit axes uses contraction."""
        return np.matmul(self.array,_array(other)) if axes is None else self.contract(other,axes)

    def contract(self, other, axes=2):
        """True NumPy tensor contraction, separate from legacy tensordot."""
        return Tensor(np.tensordot(self.array,_array(other),axes=axes))

    def tensor_power(self, power):
        if type(power) is not int or power < 0:
            raise ValueError("Tensor power must be a nonnegative integer")
        result = np.array(1)
        for _ in range(power):
            result = np.tensordot(result, self.array, axes=0)
        return Tensor(result)

    def shao_mul(self, other, start=1):
        a, b = self.array, _array(other)
        if start != 1:
            raise ValueError("Generalized product currently contracts axes 1..m-1")
        if a.ndim < 2 or not all(d == b.shape[0] for d in a.shape[1:]):
            raise ValueError("Incompatible generalized product dimensions")
        result = a
        for _ in range(a.ndim-1):
            result = np.tensordot(result, b, axes=(1, 0))
        return Tensor(result)

    def shao_mul1(self, others):
        if len(others) != self.rank-1:
            raise ValueError("One factor for each contracted tensor axis is required")
        result = self.array
        for other in others:
            result = np.tensordot(result, _array(other), axes=(1, 0))
        return Tensor(result)

    def symmetrized(self):
        if not self.is_cubical_tensor() or self.rank > 7:
            raise ValueError("Symmetrization supports cubical tensors of rank <=7")
        result = np.zeros_like(self.array, dtype=np.result_type(self.array, float))
        count = math.factorial(self.rank)
        for axes in itertools.permutations(range(self.rank)):
            result += self.array.transpose(axes)/count
        return Tensor(result, symmetric=True)

    def is_symmetric(self, epsilon=1e-6):
        if self.rank < 2:
            return True
        if not self.is_cubical_tensor():
            return False
        return all(np.allclose(self.array, self.array.swapaxes(0, i), atol=epsilon, rtol=0)
                   for i in range(1, self.rank))

    def is_diagonal_tensor(self):
        return all(len(set(index)) == 1 for index in self.to_dict())

    def sub_tensor(self, axis):
        if len(axis) != self.rank:
            raise ValueError("Provide one index list for each tensor axis")
        return Tensor(self.array[np.ix_(*axis)])

    def SpectralRadius(self, epsilon=1e-10, max_iterations=20000):
        """有限非负立方张量的谱半径和一个向量，非全部特征对。

        rank=2用数值矩阵求谱，纯对角直接处理，其余使用正向量迭代。
        可约张量可能不收敛并报错。此返回二元组不附独立残差认证；
        超图边列表优先使用Hypergraph.alpha_spectrum以避免稠密构造。
        """
        a = np.asarray(self.array, dtype=float)
        if not self.is_cubical_tensor() or self.rank < 2 or np.any(a < 0) or not np.isfinite(a).all():
            raise ValueError("Expected a finite nonnegative cubical tensor of rank >=2")
        if self.rank == 2:
            from graph_research.algebra.numeric import spectral_radius
            return spectral_radius(a)
        if self.is_diagonal_tensor():
            diagonal = [a[(i,)*self.rank] for i in range(self.shape[0])]
            x = np.zeros(self.shape[0]); x[int(np.argmax(diagonal))] = 1
            return float(max(diagonal)), x
        x = np.full(self.shape[0], 1/self.shape[0])
        for _ in range(max_iterations):
            y = a
            for _ in range(self.rank-1):
                y = np.tensordot(y, x, axes=(-1, 0))
            q = y/x**(self.rank-1)
            rho = float((q.min()+q.max())/2)
            if float(q.max()-q.min()) <= epsilon*max(1, rho):
                return rho, x
            x *= (q+1)**(1/(self.rank-1))
            x /= x.sum()
            if not np.isfinite(x).all() or np.any(x <= 0):
                break
        raise ArithmeticError("Tensor power iteration did not converge; reducible tensors may require decomposition")

    def characteristic_polynomial(self,variable="lambda",**kwargs):
        from graph_research.tensors.elimination import tensor_characteristic_polynomial
        return tensor_characteristic_polynomial(self,variable,**kwargs)

    def charpoly(self,variable="x",**kwargs): return self.characteristic_polynomial(variable,**kwargs)

    def save(self, filename):
        np.save(filename, self.array, allow_pickle=False)

    @classmethod
    def load(cls, filename):
        return cls(np.load(filename, allow_pickle=False))

    def __len__(self): return len(self.array)
    def __iter__(self): return iter(self.array)
    def __getitem__(self, key): return self.array[tuple(key) if isinstance(key, list) else key]
    def __setitem__(self, key, value): self.array[tuple(key) if isinstance(key, list) else key] = value
    def __repr__(self): return f"Tensor({self.array!r})"
    def __str__(self): return str(self.array)
    def __eq__(self, other): return np.array_equal(self.array, _array(other))
    def __ne__(self, other): return not self == other
    def __gt__(self, other): return self.array > _array(other)
    def __lt__(self, other): return self.array < _array(other)
    def __ge__(self, other): return self.array >= _array(other)
    def __le__(self, other): return self.array <= _array(other)
    def __abs__(self): return Tensor(np.abs(self.array))
    def __neg__(self): return Tensor(-self.array)
    def __add__(self, other): return Tensor(self.array+_array(other))
    def __radd__(self, other): return self+other
    def __sub__(self, other): return Tensor(self.array-_array(other))
    def __rsub__(self, other): return Tensor(_array(other)-self.array)
    def __mul__(self, other): return Tensor(self.array*_array(other))
    def __rmul__(self, other): return self*other
    def __matmul__(self, other): return self.array@_array(other)
    def __mod__(self, other): return self.array % _array(other)
    def __and__(self, other): return self.array & _array(other)
    def __or__(self, other): return self.array | _array(other)
    def __xor__(self, other): return self.array ^ _array(other)
    def __iadd__(self, other): self.array = self.array+_array(other); return self
    def __isub__(self, other): self.array = self.array-_array(other); return self
    def __bool__(self): return bool(self.array)

    def __pow__(self, power):
        if power < 0 and not self.is_diagonal_tensor():
            raise ValueError("Negative powers are supported only for diagonal tensors")
        if power < 0:
            diagonal = np.array([self.array[(i,)*self.rank] for i in range(self.shape[0])])
            if np.any(diagonal == 0):
                raise ValueError("Singular diagonal tensor")
            return DiagonalTensor(diagonal.astype(float)**power, self.rank)
        return Tensor(self.array**power)


def DiagonalTensor(D, rank=2):
    if rank < 1:
        raise ValueError("rank must be positive")
    a = np.zeros((len(D),)*rank, dtype=np.asarray(D).dtype)
    for i, value in enumerate(D):
        a[(i,)*rank] = value
    return Tensor(a, symmetric=True)


class HyperMatrix(Tensor):
    """Legacy constructor and generalized multiplication over a NumPy tensor."""
    def __init__(self, *args):
        if len(args) > 1 and all(type(i) is int for i in args):
            super().__init__(shape=args)
        elif len(args) == 1 and isinstance(args[0], tuple):
            super().__init__(shape=args[0])
        elif len(args) == 2 and callable(args[1]):
            shape, function = tuple(args[0]), args[1]
            super().__init__(np.array([function(index) for index in np.ndindex(shape)]).reshape(shape))
        elif len(args) == 2:
            shape, value = tuple(args[0]), args[1]
            super().__init__(np.full(shape, value) if np.isscalar(value) else np.asarray(value).reshape(shape))
        else:
            super().__init__(args[0])
        self.dims = list(self.shape)
        self.name = "HyperMatrix"

    @property
    def l(self): return self.array.tolist()
    def order(self): return self.rank
    def get_dims(self): return list(self.shape)
    def get_element(self, key): return self[tuple(key)]
    def set_element(self, key, value): self[tuple(key)] = value
    def apply_map(self, function): return HyperMatrix(np.vectorize(function)(self.array))
    def is_square_tensor(self): return self.is_cubical_tensor()
    def is_nonnegative(self): return bool(np.all(self.array >= 0))
    def is_positive(self): return bool(np.all(self.array > 0))
    def row_sum(self): return self.array.sum(axis=tuple(range(1, self.rank))).tolist()
    def degree_tensor(self): return diagonal_tensor(self.rank, self.row_sum())
    def reduced_order(self): return HyperMatrix(np.squeeze(self.array))
    def spectral_radius(self, niter=2000): return self.SpectralRadius(max_iterations=niter)
    def __add__(self,other):
        if self.shape!=_array(other).shape: raise ValueError("HyperMatrix dimension mismatch")
        return HyperMatrix(self.array+_array(other))
    def __sub__(self,other):
        if self.shape!=_array(other).shape: raise ValueError("HyperMatrix dimension mismatch")
        return HyperMatrix(self.array-_array(other))
    def __mul__(self, other):
        return HyperMatrix(self.array*other) if np.isscalar(other) else HyperMatrix(self.shao_mul(other).array)
    def __rmul__(self, other): return HyperMatrix(other*self.array)


def ones_hypermatrix(dims): return HyperMatrix(dims, 1)
def zeros_hypermatrix(dims): return HyperMatrix(dims, 0)
def identity_hypermatrix(dims):
    return HyperMatrix(dims, lambda index: int(len(set(index)) == 1))
def random_tensor(dims, lb, up, seed=None):
    return HyperMatrix(np.random.default_rng(seed).integers(lb, up, size=dims))
def diagonal_tensor(order, values): return HyperMatrix(DiagonalTensor(values, order).array)
HM = HyperMatrix
