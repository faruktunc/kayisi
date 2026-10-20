"""Deney faktörleri (değişkenler), sınırları ve kodlama dönüşümleri.

Kodlanmış birim: min -> -1, max -> +1. Tüm deney desenleri kodlanmış
uzayda üretilir, laboratuvara gidecek tablo gerçek birimlere çevrilir.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    unit: str
    low: float
    high: float
    # Laboratuvarda ayarlanabilecek hassasiyet (tabloyu yuvarlamak için)
    step: float

    @property
    def center(self) -> float:
        return (self.low + self.high) / 2

    @property
    def half_range(self) -> float:
        return (self.high - self.low) / 2

    def to_natural(self, coded):
        return self.center + np.asarray(coded, dtype=float) * self.half_range

    def to_coded(self, natural):
        return (np.asarray(natural, dtype=float) - self.center) / self.half_range

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "low": self.low,
            "high": self.high,
            "step": self.step,
        }


FACTORS: tuple[Factor, ...] = (
    Factor("so2_initial", "Başlangıç toplam SO₂", "ppm", 3500, 5500, 50),
    Factor("h2o2_conc", "H₂O₂ konsantrasyonu", "%", 0.5, 1.5, 0.05),
    Factor("h2o2_time", "H₂O₂ uygulama süresi", "dk", 5, 15, 0.5),
    Factor("h2o2_temp", "H₂O₂ uygulama sıcaklığı", "°C", 20, 30, 0.5),
    Factor("dry_temp", "Vakumlu kurutma sıcaklığı", "°C", 30, 60, 1),
    Factor("vacuum_pressure", "Vakum basıncı (mutlak)", "mmHg", 400, 560, 5),
)

FACTOR_KEYS: tuple[str, ...] = tuple(f.key for f in FACTORS)
N_FACTORS = len(FACTORS)


def coded_to_natural(coded: np.ndarray) -> np.ndarray:
    """(n, 6) kodlanmış matris -> (n, 6) gerçek birim matris."""
    coded = np.atleast_2d(coded)
    return np.column_stack([f.to_natural(coded[:, i]) for i, f in enumerate(FACTORS)])


def natural_to_coded(natural: np.ndarray) -> np.ndarray:
    natural = np.atleast_2d(natural)
    return np.column_stack([f.to_coded(natural[:, i]) for i, f in enumerate(FACTORS)])


def natural_from_mapping(values: dict) -> np.ndarray:
    """{'so2_initial': 4500, ...} -> (1, 6) gerçek birim satırı. Eksik anahtar merkez değeri alır.
    Model yalnızca tasarım aralığında tanımlıdır; aralık dışı değer ValueError verir."""
    unknown = set(values) - set(FACTOR_KEYS)
    if unknown:
        raise ValueError(f"Bilinmeyen faktör: {', '.join(sorted(unknown))}")
    row = []
    for f in FACTORS:
        v = float(values.get(f.key, f.center))
        if not f.low <= v <= f.high:
            raise ValueError(f"{f.label} {f.low}–{f.high} {f.unit} aralığında olmalı (verilen: {v:g})")
        row.append(v)
    return np.array([row])
