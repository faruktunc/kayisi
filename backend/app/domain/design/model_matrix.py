"""İkinci dereceden (tam kuadratik) yanıt yüzeyi modeli.

6 faktör için terimler: 1 sabit + 6 doğrusal + 15 etkileşim + 6 kare = 28.
Her terim faktör üsleri olarak tutulur; bu sayede küp üzerindeki moment
matrisi analitik olarak hesaplanabilir.
"""
from functools import lru_cache
from itertools import combinations

import numpy as np

from app.domain.shared.factors import FACTOR_KEYS, N_FACTORS


@lru_cache(maxsize=None)
def quadratic_exponents(k: int = N_FACTORS) -> tuple[tuple[int, ...], ...]:
    terms = [tuple([0] * k)]
    for i in range(k):
        e = [0] * k
        e[i] = 1
        terms.append(tuple(e))
    for i, j in combinations(range(k), 2):
        e = [0] * k
        e[i] = e[j] = 1
        terms.append(tuple(e))
    for i in range(k):
        e = [0] * k
        e[i] = 2
        terms.append(tuple(e))
    return tuple(terms)


def term_names(keys: tuple[str, ...] = FACTOR_KEYS) -> list[str]:
    names = []
    for e in quadratic_exponents(len(keys)):
        parts = []
        for key, power in zip(keys, e):
            if power == 1:
                parts.append(key)
            elif power == 2:
                parts.append(f"{key}²")
        names.append("·".join(parts) or "sabit")
    return names


def model_matrix(coded: np.ndarray) -> np.ndarray:
    coded = np.atleast_2d(np.asarray(coded, dtype=float))
    exps = np.array(quadratic_exponents(coded.shape[1]))
    # (n, 1, k) ** (1, p, k) -> çarpım -> (n, p)
    return np.prod(coded[:, None, :] ** exps[None, :, :], axis=2)


@lru_cache(maxsize=None)
def cube_moment_matrix(k: int = N_FACTORS) -> np.ndarray:
    """W = E[f(x) f(x)ᵀ], x ~ Uniform([-1, 1]^k). I-optimallik ve ortalama
    tahmin varyansı için. E[xᵉ] = 1/(e+1) (e çift), 0 (e tek)."""
    exps = np.array(quadratic_exponents(k))
    total = exps[:, None, :] + exps[None, :, :]
    per_factor = np.where(total % 2 == 0, 1.0 / (total + 1), 0.0)
    W = np.prod(per_factor, axis=2)
    W.setflags(write=False)
    return W
