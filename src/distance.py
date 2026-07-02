"""Euclidean distance matrix computation for TSPLIB EUC_2D instances.

TSPLIB convention: distances are rounded to the nearest integer using
``nint()`` (equivalent to C's ``(int)(x + 0.5)`` for positive values).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def compute_distance_matrix(coords: NDArray[np.float64]) -> NDArray[np.float64]:
    """Compute the full pairwise Euclidean distance matrix with integer rounding.

    Uses vectorized numpy operations for efficiency. The result matches
    TSPLIB's EUC_2D distance definition: ``nint(sqrt(dx² + dy²))``.

    Args:
        coords: Node coordinates of shape ``(n, 2)``.

    Returns:
        Symmetric distance matrix of shape ``(n, n)`` with float64 dtype.
        Diagonal entries are 0.0.
    """
    # Pairwise differences: shape (n, n, 2)
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]

    # Euclidean distances: shape (n, n)
    dist = np.sqrt(np.sum(diff ** 2, axis=2))

    # TSPLIB nint() rounding: floor(x + 0.5) matches C's (int)(x + 0.5)
    dist = np.floor(dist + 0.5)

    return dist
