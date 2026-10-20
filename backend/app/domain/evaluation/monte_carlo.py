"""Desenlerin sanal kayısı üzerinde Monte Carlo karşılaştırması.

Her tekrarda:
  1. Desenin deneyleri sanal prosesle 'yapılır' (ölçüm hatası eklenir)
  2. Her yanıta ikinci dereceden RSM modeli uydurulur
  3. Model, (a) bölge genelinde tahmin doğruluğu, (b) SO₂ < limit bölgesini
     doğru sınıflandırma ve (c) bulduğu optimumun GERÇEK prosesteki değeri
     açısından ölçülür.

Asıl karar ölçütü 'optimum kaybı' (regret): gerçek optimumun istenirliği ile
modelin önerdiği ayarın gerçek istenirliği arasındaki fark. 0 = mükemmel.
"""
from dataclasses import dataclass

import numpy as np

from app.domain.design.model_matrix import model_matrix
from app.domain.evaluation.desirability import Anchors, Goals, desirability
from app.domain.evaluation.optimizer import SO2_LEVELS_CODED, argmax_per_level, optimization_grid
from app.domain.evaluation.rsm import fit_quadratic
from app.domain.process.model import RESPONSE_KEYS, ProcessSettings, ProcessSimulator
from app.domain.shared.factors import FACTORS, coded_to_natural

# Optimumun 'bulundu' sayılması için gerçek istenirlikteki kayıp eşiği
SUCCESS_REGRET = 0.02
# log dönüşümü seçildiğinde ln(y) olarak modellenen (pozitif, üstel davranan) yanıtlar
LOG_RESPONSES = ("so2_final", "drying_time", "total_time")


@dataclass
class TruthReference:
    """Bir senaryo + ayar için 'gerçek' prosesin önceden hesaplanmış hali."""
    grid: np.ndarray
    grid_level: np.ndarray
    F_grid: np.ndarray
    true_grid: dict
    anchors: Anchors
    D_true: np.ndarray
    opt_idx: np.ndarray
    test_points: np.ndarray
    F_test: np.ndarray
    true_test: dict

    @classmethod
    def build(cls, simulator: ProcessSimulator, settings: ProcessSettings, goals: Goals,
              seed: int = 12345, n_test: int = 3000, grid_levels: int = 6) -> "TruthReference":
        grid, level = optimization_grid(grid_levels)
        true_grid = simulator.run(coded_to_natural(grid), settings)
        anchors = Anchors.from_responses(true_grid)
        D_true = desirability(true_grid, goals, anchors)["D"]
        rng = np.random.default_rng(seed)
        test = rng.uniform(-1, 1, (n_test, len(FACTORS)))
        return cls(grid, level, model_matrix(grid), true_grid, anchors, D_true,
                   argmax_per_level(D_true, level), test, model_matrix(test),
                   simulator.run(coded_to_natural(test), settings))

    def optimum_summary(self) -> list[dict]:
        out = []
        for lvl, idx in zip(SO2_LEVELS_CODED, self.opt_idx):
            natural = coded_to_natural(self.grid[idx])[0]
            out.append({
                "so2_initial": float(natural[0]),
                "settings": {f.key: float(v) for f, v in zip(FACTORS, natural)},
                "desirability": float(self.D_true[idx]),
                "responses": {k: float(self.true_grid[k][idx]) for k in RESPONSE_KEYS},
            })
        return out


def evaluate_design(coded: np.ndarray, simulator: ProcessSimulator, settings: ProcessSettings,
                    goals: Goals, truth: TruthReference, n_reps: int = 200,
                    noise_scale: float = 1.0, seed: int = 0, log_transform: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    natural = coded_to_natural(coded)
    F = model_matrix(coded)
    log_mask = np.array([log_transform and k in LOG_RESPONSES for k in RESPONSE_KEYS])
    n_levels = len(SO2_LEVELS_CODED)
    D_opt_true = truth.D_true[truth.opt_idx]

    true_test = np.column_stack([truth.true_test[k] for k in RESPONSE_KEYS])
    test_sd = true_test.std(axis=0)
    feasible_true_test = truth.true_test["so2_final"] <= goals.so2_limit

    regrets = np.empty((n_reps, n_levels))
    false_feasible = np.zeros((n_reps, n_levels), dtype=bool)
    nrmse = np.empty((n_reps, len(RESPONSE_KEYS)))
    class_acc = np.empty(n_reps)

    for r in range(n_reps):
        obs = simulator.run_noisy(natural, settings, rng, noise_scale)
        Y = np.column_stack([obs[k] for k in RESPONSE_KEYS])
        Y[:, log_mask] = np.log(np.maximum(Y[:, log_mask], 1e-6))
        fit = fit_quadratic(coded, Y, F)

        pred_test = fit.predict(F=truth.F_test)
        pred_test[:, log_mask] = np.exp(pred_test[:, log_mask])
        nrmse[r] = np.sqrt(np.mean((pred_test - true_test) ** 2, axis=0)) / test_sd
        class_acc[r] = np.mean((pred_test[:, 0] <= goals.so2_limit) == feasible_true_test)

        pred_grid = fit.predict(F=truth.F_grid)
        pred_grid[:, log_mask] = np.exp(pred_grid[:, log_mask])
        pred = {k: pred_grid[:, i] for i, k in enumerate(RESPONSE_KEYS)}
        D_pred = desirability(pred, goals, truth.anchors)["D"]
        idx = argmax_per_level(D_pred, truth.grid_level)
        regrets[r] = D_opt_true - truth.D_true[idx]
        false_feasible[r] = (pred["so2_final"][idx] <= goals.so2_limit) & (truth.true_grid["so2_final"][idx] > goals.so2_limit)

    mean_regret = regrets.mean(axis=1)
    return {
        "regret_mean": float(mean_regret.mean()),
        "regret_p90": float(np.quantile(mean_regret, 0.9)),
        "regret_by_level": [float(v) for v in regrets.mean(axis=0)],
        "success_rate": float(np.mean(regrets <= SUCCESS_REGRET)),
        "false_feasible_rate": float(false_feasible.mean()),
        "so2_classification_accuracy": float(class_acc.mean()),
        "nrmse": {k: float(v) for k, v in zip(RESPONSE_KEYS, nrmse.mean(axis=0))},
        "nrmse_mean": float(nrmse.mean()),
        "regret_histogram": np.histogram(mean_regret, bins=20, range=(0, max(0.2, float(mean_regret.max()))))[0].tolist(),
        "n_reps": n_reps,
        "log_transform": log_transform,
    }
