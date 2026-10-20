"""Derringer–Suich desirability: çok yanıtlı optimizasyonda her yanıt 0–1
arası bir 'istenirlik' değerine çevrilir, ağırlıklı geometrik ortalaması alınır."""
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class Goals:
    so2_limit: float = 2000.0      # ppm, yasal limit (altı tam istenir)
    so2_shape: float = 3.0         # limitin üstünde istenirliğin düşüş dikliği
    w_so2: float = 3.0
    w_time: float = 1.0
    w_L: float = 1.0
    w_dE: float = 1.0

    def __post_init__(self):
        weights = (self.w_so2, self.w_time, self.w_L, self.w_dE)
        if any(w < 0 for w in weights) or sum(weights) <= 0:
            raise ValueError("Ağırlıklar negatif olamaz ve en az biri 0'dan büyük olmalı")
        if self.so2_limit <= 0 or self.so2_shape <= 0:
            raise ValueError("SO₂ limiti ve düşüş dikliği pozitif olmalı")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Anchors:
    """Doğrusal istenirlik ölçeklerinin uçları ('gerçek' modelin bölge
    içindeki aralığından alınır; gerçek ve tahmin aynı ölçeği kullanır)."""
    so2_max: float
    time_min: float
    time_max: float
    L_min: float
    L_max: float
    dE_min: float
    dE_max: float

    @classmethod
    def from_responses(cls, r: dict) -> "Anchors":
        return cls(
            so2_max=float(np.max(r["so2_final"])),
            time_min=float(np.min(r["total_time"])), time_max=float(np.max(r["total_time"])),
            L_min=float(np.min(r["color_L"])), L_max=float(np.max(r["color_L"])),
            dE_min=float(np.min(r["color_dE"])), dE_max=float(np.max(r["color_dE"])),
        )


def _lin(y, lo, hi):
    return np.clip((y - lo) / max(hi - lo, 1e-12), 0.0, 1.0)


def desirability(r: dict, goals: Goals, anchors: Anchors) -> dict:
    so2 = np.asarray(r["so2_final"])
    over = _lin(anchors.so2_max - so2, 0.0, max(anchors.so2_max - goals.so2_limit, 1e-12))
    d_so2 = np.where(so2 <= goals.so2_limit, 1.0, over ** goals.so2_shape)
    d_time = _lin(anchors.time_max - np.asarray(r["total_time"]), 0.0, anchors.time_max - anchors.time_min)
    d_L = _lin(np.asarray(r["color_L"]), anchors.L_min, anchors.L_max)
    d_dE = _lin(anchors.dE_max - np.asarray(r["color_dE"]), 0.0, anchors.dE_max - anchors.dE_min)

    ws = np.array([goals.w_so2, goals.w_time, goals.w_L, goals.w_dE])
    ds = np.vstack([d_so2, d_time, d_L, d_dE])
    # Ağırlıklı geometrik ortalama; bir istenirlik 0 ise toplam 0
    with np.errstate(divide="ignore"):
        D = np.exp((ws[:, None] * np.log(np.maximum(ds, 1e-300))).sum(0) / ws.sum())
    # Ağırlığı 0 olan yanıt yok sayılır; ağırlıklı bir yanıtın istenirliği 0 ise toplam 0 olur
    D = np.where(np.any(ds[ws > 0] <= 0, axis=0), 0.0, D)
    return {"D": D, "d_so2": d_so2, "d_time": d_time, "d_L": d_L, "d_dE": d_dE}
