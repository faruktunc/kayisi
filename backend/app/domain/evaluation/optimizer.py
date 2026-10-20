"""Izgara üzerinde optimum arama.

Başlangıç SO₂ kontrol edilemeyen bir hammadde özelliğidir: firma gelen
partiyi seçmez, partiye göre ayar yapar. Bu yüzden optimum, her başlangıç
SO₂ seviyesi için diğer 5 faktör üzerinden ayrı ayrı aranır."""
from itertools import product

import numpy as np

from app.domain.shared.factors import N_FACTORS

SO2_LEVELS_CODED = (-1.0, 0.0, 1.0)


def optimization_grid(levels: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """(kodlanmış nokta matrisi, her noktanın SO₂ seviye indeksi)"""
    axis = np.linspace(-1, 1, levels)
    controllable = np.array(list(product(axis, repeat=N_FACTORS - 1)))
    blocks, which = [], []
    for i, s in enumerate(SO2_LEVELS_CODED):
        blocks.append(np.column_stack([np.full(len(controllable), s), controllable]))
        which.append(np.full(len(controllable), i))
    return np.vstack(blocks), np.concatenate(which)


def argmax_per_level(score: np.ndarray, level_index: np.ndarray) -> np.ndarray:
    """Her SO₂ seviyesi için en yüksek skorlu noktanın indeksi."""
    out = []
    for i in range(len(SO2_LEVELS_CODED)):
        idx = np.flatnonzero(level_index == i)
        out.append(idx[int(np.argmax(score[idx]))])
    return np.array(out)
