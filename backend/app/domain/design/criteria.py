"""Desenden doğrudan hesaplanan (yanıt verisi gerektirmeyen) istatistik ölçütler."""
import numpy as np

from app.domain.design.generators import three_level_grid
from app.domain.design.model_matrix import cube_moment_matrix, model_matrix

FDS_QUANTILES = np.linspace(0, 1, 21)


def design_criteria(coded: np.ndarray, seed: int = 0, n_fds_points: int = 5000) -> dict:
    F = model_matrix(coded)
    n, p = F.shape
    M = F.T @ F
    sign, logdet = np.linalg.slogdet(M)
    distinct = len(np.unique(np.round(coded, 6), axis=0))
    base = {
        "n_runs": n,
        "n_terms": p,
        "n_distinct": distinct,
        "n_center": int(np.sum(np.all(np.abs(coded) < 1e-9, axis=1))),
        "df_lack_of_fit": distinct - p,
        "df_pure_error": n - distinct,
        "levels_per_factor": [len(np.unique(np.round(coded[:, j], 6))) for j in range(coded.shape[1])],
    }
    if sign <= 0 or n < p:
        return {**base, "estimable": False}

    M_inv = np.linalg.inv(M)
    W = cube_moment_matrix()
    avg_var = float(np.trace(M_inv @ W))

    rng = np.random.default_rng(seed)
    pts = np.vstack([three_level_grid(), rng.uniform(-1, 1, (n_fds_points, coded.shape[1]))])
    Fp = model_matrix(pts)
    var = np.einsum("ij,jk,ik->i", Fp, M_inv, Fp)
    max_var = float(var.max())

    # VIF: kesişim hariç model sütunlarının korelasyon matrisinin tersinin köşegeni
    Z = F[:, 1:] - F[:, 1:].mean(axis=0)
    norms = np.linalg.norm(Z, axis=0)
    if np.any(norms < 1e-12):
        vif_max = float("inf")
    else:
        R = (Z / norms).T @ (Z / norms)
        vif_max = float(np.max(np.diag(np.linalg.inv(R))))

    rand_var = var[len(pts) - n_fds_points:]
    return {
        **base,
        "estimable": True,
        # Deney başına verim (farklı n'ler arasında 'verimlilik' karşılaştırması)
        "d_efficiency": float(100 * np.exp(logdet / p) / n),
        "g_efficiency": float(100 * p / (n * max_var)),
        "i_scaled": avg_var * n,
        # Mutlak hassasiyet (σ² birimi) — asıl önemli olan: daha çok deney = daha düşük
        "avg_pred_variance": avg_var,
        "max_pred_variance": max_var,
        "vif_max": vif_max,
        "fds": [float(q) for q in np.quantile(rand_var, FDS_QUANTILES)],
    }
