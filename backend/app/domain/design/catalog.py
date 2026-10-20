"""Karşılaştırılacak aday desenler (30 deney ve üzeri)."""
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.domain.design import generators as g


@dataclass(frozen=True)
class DesignSpec:
    key: str
    label: str
    family: str
    description: str
    builder: Callable[[], np.ndarray]

    def to_dict(self, n_runs: int) -> dict:
        return {"key": self.key, "label": self.label, "family": self.family,
                "description": self.description, "n_runs": n_runs}


D_OPT_CENTER_RUNS = 4


def _opt(n, crit, n_center=0):
    return lambda: g.optimal_design(n, crit, seed=n, fixed=np.zeros((n_center, 6)) if n_center else None)


DESIGN_SPECS: dict[str, DesignSpec] = {s.key: s for s in (
    DesignSpec("ccd_half", "CCD yüzey merkezli (½ faktöriyel)", "Klasik RSM",
               "2⁶⁻¹ köşe + 12 eksen + 6 merkez noktası (α = 1); her faktör 3 seviye. Klasik RSM deseni.",
               lambda: g.face_centered_ccd("half", 6)),
    DesignSpec("ccd_full", "CCD yüzey merkezli (tam faktöriyel)", "Klasik RSM",
               "2⁶ köşe + 12 eksen + 6 merkez (α = 1); üst sınır referansı olarak.",
               lambda: g.face_centered_ccd("full", 6)),
    DesignSpec("bbd", "Box-Behnken", "Klasik RSM",
               "48 kenar ortası noktası + 6 merkez; köşelere (uç kombinasyonlara) gitmez.",
               lambda: g.box_behnken_6(6)),
    *(DesignSpec(f"d_opt_{n}", f"D-optimal ({n} + {D_OPT_CENTER_RUNS} merkez)", "Optimal",
                 f"Katsayı kestirimini en iyileyen {n} nokta + {D_OPT_CENTER_RUNS} merkez tekrarı "
                 "(saf hata ve uyum eksikliği testi için). Optimal noktalar merkez tekrarları hesaba katılarak seçilir.",
                 _opt(n, "D", D_OPT_CENTER_RUNS)) for n in (30, 36, 42)),
    *(DesignSpec(f"i_opt_{n}", f"I-optimal ({n})", "Optimal",
                 "Bölge genelinde ortalama tahmin varyansını en küçükleyen desen (optimizasyon odaklı).",
                 _opt(n, "I")) for n in (30, 36, 42)),
    *(DesignSpec(f"lhs_{n}", f"Latin hiperküp ({n})", "Uzay dolduran",
                 "Maximin LHS; sürekli seviyeler (başlangıç SO₂ için her deneyde farklı parti gerekir).",
                 (lambda n=n: g.latin_hypercube(n, seed=n))) for n in (30, 42)),
)}
