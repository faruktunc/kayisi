"""Uygulama servisleri: domain nesnelerini kullanım senaryolarına göre bir araya getirir."""
from functools import lru_cache

import numpy as np

from app.domain.design.catalog import DESIGN_SPECS
from app.domain.design.criteria import design_criteria
from app.domain.evaluation.desirability import Goals
from app.domain.evaluation.monte_carlo import TruthReference, evaluate_design
from app.domain.literature.model import calibrate_so2_kinetics, predict_observations
from app.domain.process.model import ModelParameters, ProcessSettings, ProcessSimulator
from app.domain.process.scenarios import SCENARIOS
from app.domain.shared.factors import FACTORS, coded_to_natural, natural_from_mapping
from app.infrastructure.exporters import run_table_csv
from app.infrastructure.literature_repository import JsonLiteratureRepository

MAX_REPS = 1000


class LiteratureService:
    def __init__(self, repository: JsonLiteratureRepository):
        self._repo = repository
        self._fit = None

    def calibration(self):
        if self._fit is None:
            # Etkileşim terimi literatür verisinde anlamsız (≈ 0) çıkıyor; temel modelde kullanılmaz
            self._fit = calibrate_so2_kinetics(self._repo.observations(), include_interaction=False)
        return self._fit

    def calibrated_parameters(self) -> ModelParameters:
        fit = self.calibration()
        return ModelParameters(so2_ln_k0=fit.ln_k0, so2_a_conc=fit.a_conc, so2_b_temp=fit.b_temp,
                               so2_c_conc_temp=fit.c_conc_temp, so2_m_initial=fit.m_initial)

    def summary(self) -> dict:
        fit = self.calibration()
        return {
            "studies": self._repo.studies(),
            "fit": fit.to_dict(),
            "observations": predict_observations(fit, self._repo.observations()),
        }


class SimulationService:
    def __init__(self, literature: LiteratureService):
        self._literature = literature

    def parameters(self, overrides: dict | None = None) -> ModelParameters:
        return self._literature.calibrated_parameters().with_overrides(overrides)

    def simulator(self, overrides: dict | None = None) -> ProcessSimulator:
        return ProcessSimulator(self.parameters(overrides))

    def simulate(self, point: dict, settings: ProcessSettings, goals: Goals, overrides: dict | None = None) -> dict:
        sim = self.simulator(overrides)
        r = sim.run(natural_from_mapping(point), settings)
        out = {k: float(v[0]) for k, v in r.items()}
        out["meets_so2_limit"] = out["so2_final"] <= goals.so2_limit
        out["meets_moisture"] = out["moisture_final"] <= settings.target_moisture + 1e-9
        return out

    def sweep(self, point: dict, factor_key: str, settings: ProcessSettings,
              overrides: dict | None = None, n_points: int = 41) -> dict:
        """Tek bir faktörü aralığı boyunca değiştirip diğerlerini sabit tutar."""
        idx = next((i for i, f in enumerate(FACTORS) if f.key == factor_key), None)
        if idx is None:
            raise ValueError(f"Bilinmeyen faktör: {factor_key}")
        base = natural_from_mapping(point)
        X = np.repeat(base, n_points, axis=0)
        X[:, idx] = np.linspace(FACTORS[idx].low, FACTORS[idx].high, n_points)
        r = self.simulator(overrides).run(X, settings)
        return {"factor": factor_key, "x": X[:, idx].tolist(), "responses": {k: v.tolist() for k, v in r.items()}}

    def literature_optimum(self, settings: ProcessSettings, goals: Goals, overrides: dict | None = None) -> dict:
        """Literatür modeline göre her başlangıç SO₂ seviyesi için en iyi ayarlar (ızgara araması)."""
        truth = TruthReference.build(self.simulator(overrides), settings, goals, grid_levels=11)
        return {"optimum": truth.optimum_summary(), "anchors": truth.anchors.__dict__}


@lru_cache(maxsize=None)
def _design_matrix(key: str) -> np.ndarray:
    X = DESIGN_SPECS[key].builder()
    X.setflags(write=False)
    return X


class DesignService:
    def _spec(self, key: str):
        if key not in DESIGN_SPECS:
            raise ValueError(f"Bilinmeyen desen: {key}")
        return DESIGN_SPECS[key]

    def matrix(self, key: str) -> np.ndarray:
        self._spec(key)
        return _design_matrix(key)

    def catalog(self) -> list[dict]:
        return [spec.to_dict(len(self.matrix(key))) for key, spec in DESIGN_SPECS.items()]

    def criteria(self, key: str) -> dict:
        return design_criteria(self.matrix(key))

    def run_table(self, key: str, seed: int | None = 1, randomize: bool = True) -> dict:
        spec = self._spec(key)
        coded = self.matrix(key)
        natural = coded_to_natural(coded)
        order = np.random.default_rng(seed).permutation(len(coded)) if randomize else np.arange(len(coded))
        rows = []
        for run_no, std_idx in enumerate(order, start=1):
            rows.append({
                "run_order": run_no,
                "standard_order": int(std_idx) + 1,
                "coded": [float(round(v, 4)) for v in coded[std_idx]],
                "factors": {f.key: _round_to_step(natural[std_idx, i], f.step) for i, f in enumerate(FACTORS)},
            })
        return {"design": spec.to_dict(len(coded)), "rows": rows}

    def run_table_csv(self, key: str, seed: int | None = 1) -> str:
        table = self.run_table(key, seed)
        factor_cols = [(f.key, f"{f.label} ({f.unit})") for f in FACTORS]
        response_cols = ["Nihai SO₂ (ppm)", "Nihai nem (%)", "Kurutma süresi (saat)", "Toplam süre (saat)",
                         "L*", "a*", "b*", "ΔE"]
        return run_table_csv(table["rows"], factor_cols, response_cols)


def _round_to_step(value: float, step: float) -> float:
    decimals = max(0, -int(np.floor(np.log10(step)))) if step < 1 else 0
    return float(round(round(value / step) * step, decimals + 2))


class EvaluationService:
    def __init__(self, simulation: SimulationService, designs: DesignService):
        self._simulation = simulation
        self._designs = designs

    def compare(self, design_keys: list[str], scenario_keys: list[str], settings: ProcessSettings,
                goals: Goals, overrides: dict | None = None, n_reps: int = 200,
                log_transform: bool = True, seed: int = 0) -> dict:
        if not design_keys:
            raise ValueError("En az bir desen seçilmeli")
        if not scenario_keys:
            raise ValueError("En az bir senaryo seçilmeli")
        unknown = [s for s in scenario_keys if s not in SCENARIOS]
        if unknown:
            raise ValueError(f"Bilinmeyen senaryo: {', '.join(unknown)}")
        n_reps = int(min(max(n_reps, 20), MAX_REPS))

        criteria = {k: self._designs.criteria(k) for k in design_keys}
        scenarios_out = []
        for s_key in scenario_keys:
            scenario = SCENARIOS[s_key]
            merged = {**scenario.overrides, **(overrides or {})}
            sim = self._simulation.simulator(merged)
            truth = TruthReference.build(sim, settings, goals)
            results = {
                d_key: evaluate_design(self._designs.matrix(d_key), sim, settings, goals, truth,
                                       n_reps=n_reps, noise_scale=scenario.noise_scale,
                                       seed=seed, log_transform=log_transform)
                for d_key in design_keys
            }
            scenarios_out.append({"scenario": scenario.to_dict(), "optimum": truth.optimum_summary(),
                                  "results": results})

        ranking = []
        for d_key in design_keys:
            regrets = [s["results"][d_key]["regret_mean"] for s in scenarios_out]
            ranking.append({
                "design": d_key,
                "n_runs": criteria[d_key]["n_runs"],
                "regret_mean": float(np.mean(regrets)),
                "regret_worst": float(np.max(regrets)),
                "success_rate": float(np.mean([s["results"][d_key]["success_rate"] for s in scenarios_out])),
                "false_feasible_rate": float(np.mean([s["results"][d_key]["false_feasible_rate"] for s in scenarios_out])),
            })
        ranking.sort(key=lambda r: (r["regret_mean"], r["n_runs"]))
        return {
            "settings": {"n_applications": settings.n_applications, "target_moisture": settings.target_moisture},
            "goals": goals.to_dict(),
            "n_reps": n_reps,
            "log_transform": log_transform,
            "criteria": criteria,
            "scenarios": scenarios_out,
            "ranking": ranking,
            "recommendation": _recommend(ranking),
        }


def _recommend(ranking: list[dict]) -> dict:
    """Dirsek kuralı: en iyi ortalama kayba göre en fazla %25 (ve 0,005) kötü olan
    desenler arasından en az deneyli olanı önerir."""
    best = min(r["regret_mean"] for r in ranking)
    tolerance = max(best * 1.25, best + 0.005)
    eligible = [r for r in ranking if r["regret_mean"] <= tolerance]
    choice = min(eligible, key=lambda r: (r["n_runs"], r["regret_mean"]))
    return {"design": choice["design"], "best_regret": best, "tolerance": tolerance,
            "eligible": [r["design"] for r in eligible]}

