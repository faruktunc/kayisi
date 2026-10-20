"""Deney deseni üreteçleri. Hepsi kodlanmış uzayda [-1, 1]^6 matris döndürür."""
from itertools import product

import numpy as np

from app.domain.design.model_matrix import cube_moment_matrix, model_matrix
from app.domain.shared.factors import N_FACTORS

# 6 faktörlü Box-Behnken için standart dengeli tamamlanmamış blok yapısı
# (her satırdaki üç faktör 2³ faktöriyelle değiştirilir, diğerleri merkezde)
BBD6_BLOCKS = ((0, 1, 3), (1, 2, 4), (2, 3, 5), (0, 3, 4), (1, 4, 5), (0, 2, 5))


def _center(n_center: int, k: int = N_FACTORS) -> np.ndarray:
    return np.zeros((n_center, k))


def full_factorial_2level(k: int) -> np.ndarray:
    return np.array(list(product([-1.0, 1.0], repeat=k)))


def face_centered_ccd(fraction: str = "half", n_center: int = 6, k: int = N_FACTORS) -> np.ndarray:
    """Yüzey merkezli merkezi kompozit desen (α = 1, 3 seviye).
    fraction='half': 2^(6-1), x6 = x1·x2·x3·x4·x5 (çözünürlük VI)."""
    if fraction == "full":
        cube = full_factorial_2level(k)
    elif fraction == "half":
        base = full_factorial_2level(k - 1)
        cube = np.column_stack([base, np.prod(base, axis=1)])
    else:
        raise ValueError("fraction 'full' ya da 'half' olmalı")
    axial = np.vstack([np.eye(k), -np.eye(k)])
    return np.vstack([cube, axial, _center(n_center, k)])


def box_behnken_6(n_center: int = 6) -> np.ndarray:
    runs = []
    for block in BBD6_BLOCKS:
        for signs in product([-1.0, 1.0], repeat=3):
            row = np.zeros(N_FACTORS)
            row[list(block)] = signs
            runs.append(row)
    return np.vstack([np.array(runs), _center(n_center)])


def latin_hypercube(n_runs: int, seed: int = 0, iterations: int = 300, k: int = N_FACTORS) -> np.ndarray:
    """Maximin Latin hiperküp (sürekli seviyeler, uzay dolduran)."""
    rng = np.random.default_rng(seed)
    best, best_score = None, -np.inf
    for _ in range(iterations):
        cols = [(rng.permutation(n_runs) + rng.uniform(0, 1, n_runs)) / n_runs for _ in range(k)]
        X = 2 * np.column_stack(cols) - 1
        d = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
        score = d[np.triu_indices(n_runs, 1)].min()
        if score > best_score:
            best, best_score = X, score
    return best


def three_level_grid(k: int = N_FACTORS) -> np.ndarray:
    return np.array(list(product([-1.0, 0.0, 1.0], repeat=k)))


def optimal_design(n_runs: int, criterion: str = "D", seed: int = 0, n_starts: int = 4,
                   candidates: np.ndarray | None = None, max_passes: int = 30,
                   fixed: np.ndarray | None = None) -> np.ndarray:
    """Fedorov tipi nokta değiştirme algoritması.

    criterion='D': det(FᵀF) en büyük (katsayı kestirimi)
    criterion='I': ortalama tahmin varyansı trace((FᵀF)⁻¹W) en küçük (tahmin / optimizasyon)
    Aday küme varsayılan olarak 3^6 = 729 noktalı ızgaradır (her faktör 3 seviye;
    başlangıç SO₂ için yalnızca 3 parti seviyesi gerekir).

    fixed: desende zorunlu tutulan noktalar (örn. merkez tekrarları). Bilgi
    matrisine dahil edilir, değiştirilmez; serbest n_runs nokta bunları
    tamamlayacak şekilde seçilir. Dönen desen = fixed + serbest noktalar."""
    if criterion not in ("D", "I"):
        raise ValueError("criterion 'D' ya da 'I' olmalı")
    cand = three_level_grid() if candidates is None else candidates
    Fc = model_matrix(cand)
    p = Fc.shape[1]
    fixed = np.zeros((0, cand.shape[1])) if fixed is None else np.atleast_2d(fixed)
    M_fixed = model_matrix(fixed).T @ model_matrix(fixed) if len(fixed) else np.zeros((p, p))
    if n_runs + len(fixed) < p:
        raise ValueError(f"Tam kuadratik model için en az {p} deney gerekir")
    W = cube_moment_matrix()
    rng = np.random.default_rng(seed)

    def score(M_inv, logdet):
        return -logdet if criterion == "D" else float(np.trace(M_inv @ W))

    best_idx, best_score = None, np.inf
    for _ in range(n_starts):
        for _attempt in range(100):
            idx = rng.choice(len(cand), n_runs, replace=False)
            M = M_fixed + Fc[idx].T @ Fc[idx]
            sign, logdet = np.linalg.slogdet(M)
            if sign > 0 and logdet > -200:
                break
        else:
            raise RuntimeError("Tekil olmayan başlangıç deseni bulunamadı")

        M_inv = np.linalg.inv(M)
        current = score(M_inv, logdet)
        for _pass in range(max_passes):
            improved = False
            for i in range(n_runs):
                fi = Fc[idx[i]]
                Mfi = M_inv @ fi
                di = fi @ Mfi
                if di >= 1 - 1e-10:
                    continue
                # i. noktayı çıkar (Sherman–Morrison)
                A_inv = M_inv + np.outer(Mfi, Mfi) / (1 - di)
                U = Fc @ A_inv
                dc = np.einsum("ij,ij->i", U, Fc)
                if criterion == "D":
                    new = -(logdet + np.log(1 - di) + np.log1p(dc))
                else:
                    base_trace = np.trace(A_inv @ W)
                    q = np.einsum("ij,ij->i", U @ W, U)
                    new = base_trace - q / (1 + dc)
                j = int(np.argmin(new))
                if new[j] < current - 1e-9 * max(1.0, abs(current)):
                    idx[i] = j
                    M = M_fixed + Fc[idx].T @ Fc[idx]
                    M_inv = np.linalg.inv(M)
                    logdet = np.linalg.slogdet(M)[1]
                    current = score(M_inv, logdet)
                    improved = True
            if not improved:
                break
        if current < best_score:
            best_idx, best_score = idx.copy(), current
    return np.vstack([fixed, cand[best_idx]])
