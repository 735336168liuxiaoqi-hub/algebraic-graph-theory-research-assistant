"""Public functional API; compatibility names remain available."""
from graph_research.tensors.core import DiagonalTensor, HyperMatrix, Tensor, diagonal_tensor, identity_hypermatrix, ones_hypermatrix, random_tensor, zeros_hypermatrix
__all__ = ['DiagonalTensor', 'HyperMatrix', 'Tensor', 'diagonal_tensor', 'identity_hypermatrix', 'ones_hypermatrix', 'random_tensor', 'zeros_hypermatrix']
def __dir__(): return sorted(set(globals()) | set(__all__))
