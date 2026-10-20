"""İkinci dereceden RSM modelinin en küçük kareler uyumu."""
from dataclasses import dataclass

import numpy as np

from app.domain.design.model_matrix import model_matrix


@dataclass(frozen=True)
class QuadraticFit:
    coefficients: np.ndarray  # (p, n_yanıt)

    def predict(self, coded: np.ndarray | None = None, F: np.ndarray | None = None) -> np.ndarray:
        F = model_matrix(coded) if F is None else F
        return F @ self.coefficients


def fit_quadratic(coded: np.ndarray, Y: np.ndarray, F: np.ndarray | None = None) -> QuadraticFit:
    F = model_matrix(coded) if F is None else F
    beta, *_ = np.linalg.lstsq(F, Y, rcond=None)
    return QuadraticFit(beta)
