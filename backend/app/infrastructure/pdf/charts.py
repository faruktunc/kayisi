"""Rapor grafikleri (matplotlib → PNG)."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ACCENT = "#c8691c"
FAMILY_COLORS = {"Klasik RSM": "#c8691c", "Optimal": "#2e6fa8", "Uzay dolduran": "#7a5ba6"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e3d8", "grid.linestyle": "--", "axes.edgecolor": "#7a7468",
})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def regret_scatter(points: list[dict], recommended: str | None = None) -> bytes:
    """points: [{key, short, n, regret, family}]"""
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    for fam, color in FAMILY_COLORS.items():
        pts = [p for p in points if p["family"] == fam]
        if pts:
            ax.scatter([p["n"] for p in pts], [p["regret"] for p in pts], s=36, color=color, label=fam, zorder=3)
    for p in points:
        bold = p["key"] == recommended
        ax.annotate(p["short"], (p["n"], p["regret"]), textcoords="offset points", xytext=(0, 6),
                    ha="center", fontsize=7, fontweight="bold" if bold else "normal")
        if bold:
            ax.scatter([p["n"]], [p["regret"]], s=140, facecolors="none", edgecolors=ACCENT, linewidths=1.5, zorder=4)
    ax.set_xlabel("Deney sayısı")
    ax.set_ylabel("Ortalama optimum kaybı")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    return _png(fig)


def sweep_grid(panels: list[dict], ylabel: str, hline: float | None = None) -> bytes:
    """panels: [{title, x, y, current}] — 2×3 küçük çoklu grafik."""
    fig, axes = plt.subplots(2, 3, figsize=(7.5, 4.2), sharey=True)
    for ax, panel in zip(axes.flat, panels):
        ax.plot(panel["x"], panel["y"], color=ACCENT, lw=1.8)
        ax.axvline(panel["current"], color="#7a7468", lw=0.8, ls=":")
        if hline is not None:
            ax.axhline(hline, color="#b8322a", lw=0.9, ls="--")
        ax.set_title(panel["title"], fontsize=7.5)
        ax.tick_params(labelsize=6.5)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    fig.tight_layout()
    return _png(fig)
