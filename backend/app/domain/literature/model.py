"""Literatür gözlemleri ve SO₂ kinetiği kalibrasyonu.

H₂O₂ uygulamasında SO₂ azalması birinci dereceden kinetikle tanımlanır:

    SO₂(t) = SO₂₀ · exp(-k · t)

Gözlenen hız sabiti, log-doğrusal bir modelle açıklanır:

    ln k = ln k₀ + a·ln(C) + b·(T − 25) + c·ln(C)·(T − 25) − m·ln(SO₂₀ / 4500) + grup etkisi

Grup etkisi (çalışma / çeşit farkı) toplamı sıfır olacak şekilde kodlanır;
simülatör ortalama grubu (etki = 0) kullanır.
"""
from dataclasses import asdict, dataclass

import numpy as np

S0_REF = 4500.0
T_REF = 25.0
# k çok küçük çıkan (neredeyse hiç azalmayan) noktalarda ln k patlamasın
MIN_RELATIVE_REDUCTION = 0.005


@dataclass(frozen=True)
class Observation:
    study: str
    group: str
    sample: str
    h2o2_conc: float
    temp: float
    time: float
    so2_initial: float
    so2: float
    sd: float | None

    @property
    def observed_k(self) -> float:
        ratio = min(self.so2 / self.so2_initial, 1 - MIN_RELATIVE_REDUCTION)
        return -np.log(ratio) / self.time


@dataclass(frozen=True)
class So2KineticFit:
    ln_k0: float
    a_conc: float
    b_temp: float
    c_conc_temp: float
    m_initial: float
    group_effects: dict
    r2_ln_k: float
    r2_so2: float
    rmse_so2: float
    n_obs: int

    def to_dict(self) -> dict:
        return asdict(self)


def _design_row(conc, temp, s0):
    ln_c = np.log(conc)
    dt = temp - T_REF
    return [1.0, ln_c, dt, ln_c * dt, -np.log(s0 / S0_REF)]


def calibrate_so2_kinetics(observations: list[Observation], include_interaction: bool = True) -> So2KineticFit:
    groups = sorted({o.group for o in observations})
    rows, y = [], []
    for o in observations:
        row = _design_row(o.h2o2_conc, o.temp, o.so2_initial)
        # Toplamı sıfır grup kodlaması: son grup diğerlerinin eksi toplamı
        dummies = [(1.0 if o.group == g else 0.0) - (1.0 if o.group == groups[-1] else 0.0) for g in groups[:-1]]
        rows.append(row + dummies)
        y.append(np.log(o.observed_k))
    X = np.array(rows)
    y = np.array(y)
    if not include_interaction:
        X[:, 3] = 0.0
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)

    resid = y - X @ beta
    r2_ln_k = 1 - resid @ resid / np.sum((y - y.mean()) ** 2)

    k_hat = np.exp(X @ beta)
    s0 = np.array([o.so2_initial for o in observations])
    t = np.array([o.time for o in observations])
    s_obs = np.array([o.so2 for o in observations])
    s_hat = s0 * np.exp(-k_hat * t)
    r2_so2 = 1 - np.sum((s_obs - s_hat) ** 2) / np.sum((s_obs - s_obs.mean()) ** 2)

    effects = {g: float(beta[5 + i]) for i, g in enumerate(groups[:-1])}
    effects[groups[-1]] = float(-sum(effects.values()))
    return So2KineticFit(
        ln_k0=float(beta[0]),
        a_conc=float(beta[1]),
        b_temp=float(beta[2]),
        c_conc_temp=float(beta[3]),
        m_initial=float(beta[4]),
        group_effects=effects,
        r2_ln_k=float(r2_ln_k),
        r2_so2=float(r2_so2),
        rmse_so2=float(np.sqrt(np.mean((s_obs - s_hat) ** 2))),
        n_obs=len(observations),
    )


def predict_observations(fit: So2KineticFit, observations: list[Observation], use_group_effect: bool = True) -> list[dict]:
    """Gözlenen ve model tahmini SO₂ değerlerini yan yana döndürür (kalibrasyon grafiği için)."""
    out = []
    for o in observations:
        row = np.array(_design_row(o.h2o2_conc, o.temp, o.so2_initial))
        coef = np.array([fit.ln_k0, fit.a_conc, fit.b_temp, fit.c_conc_temp, fit.m_initial])
        ln_k = row @ coef + (fit.group_effects.get(o.group, 0.0) if use_group_effect else 0.0)
        pred = o.so2_initial * np.exp(-np.exp(ln_k) * o.time)
        out.append({**asdict(o), "predicted": float(pred)})
    return out
