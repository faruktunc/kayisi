"""PDF raporlarının içeriğini kuran servis. Dizgi: infrastructure.pdf."""
from collections import Counter
from dataclasses import dataclass

from app.application.services import DesignService, LiteratureService, SimulationService
from app.domain.design.catalog import DESIGN_SPECS
from app.domain.evaluation.desirability import Goals
from app.domain.process.model import PARAMETER_GROUPS, ProcessSettings
from app.domain.shared.factors import FACTORS
from app.infrastructure.pdf import charts
from app.infrastructure.pdf.renderer import Report, TableBlock, render

ASSUMPTION_NOTE = ("SO₂ kinetiği iki literatür çalışmasından (Özkan & Cemeroğlu; Uğur & Erdoğan) kalibre edilmiştir. "
                   "Kurutma ve renk modelleri bu ürüne ait veri olmadığından varsayımdır. Sonuçlar gerçek ölçüm yerine "
                   "geçmez; desen seçimi ve aralıkların sınanması içindir.")

RESPONSE_SHORT = {"so2_final": "SO₂", "drying_time": "Kurutma s.", "total_time": "Toplam s.",
                  "color_L": "L*", "color_dE": "ΔE"}


# Dar tablo sütunları için kısa faktör başlıkları (birim alt satırda)
SHORT_FACTOR = {"so2_initial": "Başl. SO₂", "h2o2_conc": "H₂O₂ kons.", "h2o2_time": "H₂O₂ süresi",
                "h2o2_temp": "H₂O₂ sıcaklığı", "dry_temp": "Kurutma sıcaklığı", "vacuum_pressure": "Vakum basıncı"}


def _col(f) -> str:
    return f"{SHORT_FACTOR[f.key]}<br/>({f.unit})"


BLANK = "................................"
PRESSURE_MODES = {
    "absolute": "Mutlak basınç: vakum pompası, hazne içi basınç tablodaki değere inecek şekilde ayarlanır.",
    "gauge": "Vakum göstergesi değeri: gösterge, atmosferin tablodaki değer kadar altını gösterecek şekilde ayarlanır.",
}


@dataclass(frozen=True)
class RunSheetConditions:
    """Föyde tüm deneylerde sabit tutulan koşullar. None = henüz kararlaştırılmadı,
    föyde doldurulacak alan olarak basılır."""
    n_applications: int | None = None
    target_moisture: float | None = None
    pressure_mode: str | None = None

    def __post_init__(self):
        if self.n_applications is not None and not 1 <= self.n_applications <= 5:
            raise ValueError("Uygulama sayısı 1 ile 5 arasında olmalı")
        if self.target_moisture is not None and not 10 <= self.target_moisture <= 35:
            raise ValueError("Hedef nem %10 ile %35 arasında olmalı")
        if self.pressure_mode is not None and self.pressure_mode not in PRESSURE_MODES:
            raise ValueError("pressure_mode 'absolute' ya da 'gauge' olmalı")


def tr(value, digits: int = 1) -> str:
    """Türkçe sayı biçimi: 1.234,5"""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v != v:
        return "—"
    if v in (float("inf"), float("-inf")):
        return "∞"
    s = f"{v:,.{digits}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(value, digits: int = 0) -> str:
    return "%" + tr(100 * float(value), digits)


def hours(h) -> str:
    h = float(h)
    hh, mm = int(h), round((h - int(h)) * 60)
    if mm == 60:
        hh, mm = hh + 1, 0
    return f"{hh} sa {mm} dk"


def _factor_digits(f) -> int:
    return 2 if f.step < 0.1 else 1 if f.step < 1 else 0


def _short(key: str) -> str:
    return {"ccd_half": "CCD½", "ccd_full": "CCD", "bbd": "BBD"}.get(
        key, key.replace("d_opt_", "D").replace("i_opt_", "I").replace("lhs_", "LHS"))


def _label(key: str) -> str:
    spec = DESIGN_SPECS.get(key)
    return spec.label if spec else key


def _settings_pairs(settings: dict, goals: dict) -> list[tuple[str, str]]:
    return [
        ("H₂O₂ uygulama sayısı", str(settings.get("n_applications"))),
        ("Hedef nem", f"%{tr(settings.get('target_moisture'), 1)} (kurutma bu neme inince biter)"),
        ("SO₂ limiti", f"{tr(goals.get('so2_limit'), 0)} ppm"),
        ("Ağırlıklar (SO₂ / süre / L* / ΔE)",
         " / ".join(tr(goals.get(k), 1) for k in ("w_so2", "w_time", "w_L", "w_dE"))),
    ]


def _optimum_table(optimum: list[dict], so2_limit: float) -> TableBlock:
    controllable = FACTORS[1:]
    rows = []
    for o in optimum:
        so2 = o["responses"]["so2_final"]
        rows.append([
            f"<b>{tr(o['so2_initial'], 0)}</b>",
            *[tr(o["settings"][f.key], _factor_digits(f)) for f in controllable],
            f"<font color='{'#2f7d4f' if so2 <= so2_limit else '#b8322a'}'><b>{tr(so2, 0)}</b></font>",
            hours(o["responses"]["total_time"]),
            tr(o["responses"]["color_L"], 1),
            tr(o["responses"]["color_dE"], 1),
            tr(o["desirability"], 3),
        ])
    return TableBlock(
        columns=["Başl. SO₂<br/>(ppm)", *[_col(f) for f in controllable],
                 "Nihai SO₂", "Toplam süre", "L*", "ΔE", "D"],
        rows=rows, col_widths=[1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 0.9, 1.0, 0.6, 0.6, 0.6])


class ReportService:
    def __init__(self, simulation: SimulationService, designs: DesignService, literature: LiteratureService):
        self._simulation = simulation
        self._designs = designs
        self._literature = literature

    # --- Desen karşılaştırma raporu -------------------------------------------------
    def comparison_pdf(self, result: dict) -> bytes:
        required = ("ranking", "recommendation", "criteria", "scenarios", "settings", "goals")
        missing = [k for k in required if k not in result]
        if missing:
            raise ValueError(f"Karşılaştırma sonucu eksik: {', '.join(missing)}")
        unknown = [r["design"] for r in result["ranking"] if r["design"] not in DESIGN_SPECS]
        if unknown:
            raise ValueError(f"Bilinmeyen desen: {', '.join(unknown)}")

        settings, goals = result["settings"], result["goals"]
        rec = result["recommendation"]
        rec_n = result["criteria"][rec["design"]]["n_runs"]
        rep = Report("Deney deseni karşılaştırma raporu",
                     "Kuru kayısı desülfitleme · ardışık H₂O₂ uygulaması + vakumlu kurutma · "
                     "literatür tabanlı sanal model üzerinde Monte Carlo karşılaştırması")
        rep.callout(f"<b>Önerilen desen: {_label(rec['design'])} — {rec_n} deney</b><br/>"
                    f"En iyi ortalama optimum kaybı {tr(rec['best_regret'], 4)}; tolerans {tr(rec['tolerance'], 4)}. "
                    f"Tolerans içindeki desenler: {', '.join(_label(k) for k in rec['eligible'])}. "
                    "Bunlar arasından en az deneyli olan önerilmiştir.")

        rep.heading("Ayarlar")
        rep.key_values(_settings_pairs(settings, goals) + [
            ("Monte Carlo tekrarı", str(result.get("n_reps"))),
            ("Log dönüşümü (SO₂, süreler)", "Evet" if result.get("log_transform") else "Hayır"),
            ("Senaryolar", ", ".join(s["scenario"]["label"] for s in result["scenarios"])),
            ("Karşılaştırılan desen sayısı", str(len(result["ranking"]))),
        ])

        rep.heading("Yöntem")
        rep.paragraph(
            "1) <b>İstatistik ölçütler</b> desenden doğrudan hesaplanır (yanıt gerektirmez). "
            "2) <b>Monte Carlo:</b> her desen sanal proseste tekrar tekrar uygulanır, ölçüm hatası eklenir ve her yanıta "
            "ikinci dereceden RSM modeli uydurulur. 3) <b>Optimum kaybı:</b> modelin desirability ile önerdiği ayarın "
            "gerçek istenirliği, gerçek optimumla kıyaslanır (0 = mükemmel). Başlangıç SO₂ hammadde özelliği "
            "olduğundan her parti seviyesi (3500 / 4500 / 5500 ppm) için ayrı hesaplanır. 4) <b>Sağlamlık:</b> "
            "değerlendirme farklı 'gerçek' senaryolarda tekrarlanır. 5) <b>Karar:</b> en iyi ortalama kayba %25 "
            "(en az 0,005) yakın desenler arasından en az deneyli olan önerilir.")

        rep.heading("Deney sayısı – optimum kaybı")
        points = [{"key": r["design"], "short": _short(r["design"]), "n": r["n_runs"],
                   "regret": r["regret_mean"], "family": DESIGN_SPECS[r["design"]].family}
                  for r in result["ranking"]]
        rep.image(charts.regret_scatter(points, rec["design"]), 0.9)
        rep.note("D/I = D-/I-optimal, LHS = Latin hiperküp, CCD½ = yarım faktöriyel CCD. Halkalı nokta önerilen desendir.")

        rep.heading("Sıralama ve istatistik ölçütler")
        rows, highlight = [], set()
        for i, r in enumerate(result["ranking"]):
            c = result["criteria"][r["design"]]
            if r["design"] == rec["design"]:
                highlight.add(i)
            rows.append([_label(r["design"]), r["n_runs"], f"<b>{tr(r['regret_mean'], 4)}</b>",
                         tr(r["regret_worst"], 4), pct(r["success_rate"]), pct(r["false_feasible_rate"]),
                         tr(c.get("d_efficiency"), 1), tr(c.get("g_efficiency"), 1),
                         tr(c.get("avg_pred_variance"), 3), tr(c.get("vif_max"), 2), c.get("df_pure_error")])
        rep.table(TableBlock(
            columns=["Desen", "Deney", "Ort. kayıp", "En kötü senaryo", "Başarı", "Yanlış uygun",
                     "D-verim", "G-verim", "Ort. tahmin var.", "Maks. VIF", "Saf hata sd"],
            rows=rows, highlight_rows=highlight, col_widths=[2.3, 0.85, 0.9, 1.0, 0.8, 0.9, 0.95, 0.95, 1.0, 0.8, 0.75]))
        rep.note("Başarı: optimum kaybı ≤ 0,02 olan tekrar oranı. Yanlış uygun: model SO₂ limitinin altında der, "
                 "gerçekte üstündedir. Saf hata sd = 0 olan desenlerde uyum eksikliği testi yapılamaz.")

        rep.heading("Senaryo × desen optimum kaybı")
        scen = result["scenarios"]
        rep.table(TableBlock(
            columns=["Desen", *[s["scenario"]["label"] for s in scen]],
            rows=[[_label(r["design"]), *[tr(s["results"][r["design"]]["regret_mean"], 4) for s in scen]]
                  for r in result["ranking"]],
            col_widths=[2.6, *[1.2] * len(scen)]))

        for s in scen:
            rep.heading(f"Senaryo: {s['scenario']['label']}")
            rep.note(s["scenario"]["description"])
            rep.lead("<b>Gerçek optimum</b> (sanal modele göre, her başlangıç SO₂ seviyesi için):")
            rep.table(_optimum_table(s["optimum"], goals["so2_limit"]))
            rep.lead("<b>Normalleştirilmiş tahmin hatası</b> (RMSE / yanıt SD):")
            rep.table(TableBlock(
                columns=["Desen", *RESPONSE_SHORT.values(), "SO₂ sınıflandırma"],
                rows=[[_label(r["design"]),
                       *[tr(s["results"][r["design"]]["nrmse"][k], 3) for k in RESPONSE_SHORT],
                       pct(s["results"][r["design"]]["so2_classification_accuracy"], 1)]
                      for r in result["ranking"]],
                col_widths=[2.6, 0.9, 0.9, 0.9, 0.9, 0.9, 1.1]))

        rep.heading("Not")
        rep.note(ASSUMPTION_NOTE)
        return render(rep)

    # --- Laboratuvar deney föyü --------------------------------------------------------
    def run_table_pdf(self, key: str, seed: int = 1, conditions: RunSheetConditions | None = None) -> bytes:
        cond = conditions or RunSheetConditions()
        table = self._designs.run_table(key, seed)
        c = self._designs.criteria(key)
        d = table["design"]
        rep = Report(f"Deney föyü — {d['label']}",
                     "Kuru kayısı desülfitleme · ardışık H₂O₂ uygulaması + vakumlu kurutma · "
                     "Yanıt Yüzeyi Yöntemi (RSM) deney planı", landscape=True)
        rep.key_values([
            ("Desen", f"{d['label']} · {d['n_runs']} deney"),
            ("Sıra tohumu", str(seed)),
            ("Merkez noktası", str(c["n_center"])),
            ("Saf hata / uyum eksikliği sd", f"{c['df_pure_error']} / {c['df_lack_of_fit']}"),
            ("Tarih", BLANK),
            ("Sorumlu", BLANK),
        ], columns=3)
        rep.note(d["description"])

        rep.heading("Sabit proses koşulları (tüm deneylerde aynı)")
        n_app = (f"<b>{cond.n_applications}</b>" if cond.n_applications
                 else f"{BLANK} <font color='#b8322a'>(kararlaştırılacak)</font>")
        moisture = (f"<b>%{tr(cond.target_moisture, 1)}</b> (yaş baz)" if cond.target_moisture is not None
                    else f"% {BLANK} (yaş baz; son ürün hedefi %20–25 arasından tek bir değer)")
        if cond.pressure_mode:
            pressure = f"<b>{PRESSURE_MODES[cond.pressure_mode]}</b>"
        else:
            pressure = ("☐ Mutlak basınç (hazne içi basınç)&nbsp;&nbsp;&nbsp;☐ Vakum göstergesi (atmosferin altı) "
                        "<font color='#b8322a'>(kararlaştırılacak)</font>")
        rep.table(TableBlock(
            columns=["Koşul", "Değer", "Açıklama"],
            rows=[
                ["H₂O₂ uygulama sayısı", n_app,
                 "Her uygulamada tablodaki konsantrasyon, süre ve sıcaklık kullanılır; çözelti her uygulamada tazelenir."],
                ["Uygulamalar arası süzdürme", f"{BLANK} dk", "Birden çok uygulama varsa ürün bu süre süzdürülür."],
                ["Çözelti / meyve oranı", f"{BLANK} (a/a)", "Tüm deneylerde aynı tutulur."],
                ["Kurutmanın bitişi", moisture,
                 "Kurutma, ürün bu neme inince durdurulur; geçen süre 'Kurutma süresi' sütununa yazılır."],
                ["Vakum basıncı", pressure, "Tablodaki 400–560 mmHg değerleri bu tanıma göre ayarlanır."],
                ["Nem tayini", BLANK, "Yöntem / cihaz (örn. etüv, 105 °C; nem tayin cihazı)."],
                ["SO₂ analizi", BLANK, "Yöntem (örn. Monier-Williams); her örnekte aynı."],
                ["Renk ölçümü", "CIE L*a*b*, D65 / 10°",
                 "Her deneyden en az 5 meyve, iki yüzden ölçülür; ortalama yazılır. ΔE ticari kükürtlü ürüne göre hesaplanır."],
            ],
            col_widths=[1.4, 2.6, 3.6]))

        rep.heading("Ham madde partileri")
        so2 = next(f for f in FACTORS if f.key == "so2_initial")
        counts = Counter(r["factors"]["so2_initial"] for r in table["rows"])
        rep.table(TableBlock(
            columns=["Parti", "Hedef başlangıç SO₂ (ppm)", "Deney sayısı", "Ölçülen başlangıç SO₂ (ppm)",
                     "Parti no / geliş tarihi", "Not"],
            rows=[[chr(ord("A") + i), tr(level, 0), counts[level], "", "", ""]
                  for i, level in enumerate(sorted(counts))],
            row_height=8, col_widths=[0.6, 1.4, 1.0, 1.6, 1.8, 1.6]))
        rep.note(f"Her parti, tablodaki deneylerin tümüne yetecek miktarda ayrılmalıdır. Partinin gerçek SO₂ düzeyi "
                 f"ölçülüp kaydedilmelidir; modelde hedef değer yerine ölçülen değer kullanılır "
                 f"(tasarım aralığı {tr(so2.low, 0)}–{tr(so2.high, 0)} ppm).")

        rep.page_break()
        rep.heading("Deney sırası")
        rep.note("Deneyler 'Sıra' sütunundaki rastgele sırayla yapılmalıdır (zamana bağlı etkiler bu sayede dağılır). "
                 "'Desen no' standart sıradır; analizde eşleştirme içindir.")
        rows = []
        for r in table["rows"]:
            rows.append([r["run_order"], r["standard_order"],
                         *[tr(r["factors"][f.key], _factor_digits(f)) for f in FACTORS],
                         "", "", "", "", "", "", ""])
        rep.table(TableBlock(
            columns=["Sıra", "Desen no", *[_col(f) for f in FACTORS],
                     "Nihai SO₂<br/>(ppm)", "Nihai nem<br/>(%)", "Kurutma<br/>süresi (sa)", "L*", "a*", "b*", "Not"],
            rows=rows, row_height=7.5,
            col_widths=[0.45, 0.55, 0.95, 0.85, 0.8, 0.8, 0.85, 0.85, 0.85, 0.75, 0.8, 0.5, 0.5, 0.5, 1.3]))
        return render(rep)

    # --- Simülasyon raporu --------------------------------------------------------------
    def simulation_pdf(self, point: dict, settings: ProcessSettings, goals: Goals, overrides: dict | None) -> bytes:
        sim = self._simulation
        r = sim.simulate(point, settings, goals, overrides)
        rep = Report("Simülasyon raporu",
                     "Kuru kayısı desülfitleme · literatür tabanlı sanal kayısı modeli")
        rep.heading("Proses ayarları")
        rep.key_values(
            [(f"{f.label}", f"{tr(point.get(f.key, f.center), _factor_digits(f))} {f.unit}") for f in FACTORS]
            + _settings_pairs({"n_applications": settings.n_applications,
                               "target_moisture": settings.target_moisture}, goals.to_dict()))

        rep.heading("Sonuçlar")
        so2_ok = r["so2_final"] <= goals.so2_limit
        rep.callout(f"Nihai toplam SO₂: <b>{tr(r['so2_final'], 0)} ppm</b> — "
                    + (f"<font color='#2f7d4f'>{tr(goals.so2_limit, 0)} ppm limit sağlanıyor</font>" if so2_ok
                       else f"<font color='#b8322a'>{tr(goals.so2_limit, 0)} ppm limitin üstünde</font>")
                    + f" · Toplam işlem süresi: <b>{hours(r['total_time'])}</b>")
        rep.key_values([
            ("H₂O₂ sonrası SO₂", f"{tr(r['so2_after_dip'], 0)} ppm"),
            ("H₂O₂ sonrası nem", f"%{tr(r['moisture_after_dip'], 1)}"),
            ("Nihai nem", f"%{tr(r['moisture_final'], 1)}"),
            ("Kurutma süresi", hours(r["drying_time"])),
            ("L* / a* / b*", f"{tr(r['color_L'], 1)} / {tr(r['color_a'], 1)} / {tr(r['color_b'], 1)}"),
            ("ΔE (ticari kükürtlü ürüne göre)", tr(r["color_dE"], 1)),
        ])

        for resp, ylabel, hline in (("so2_final", "Nihai SO₂ (ppm)", goals.so2_limit),
                                    ("total_time", "Toplam süre (saat)", None)):
            panels = []
            for f in FACTORS:
                sw = sim.sweep(point, f.key, settings, overrides, n_points=31)
                panels.append({"title": f"{f.label} ({f.unit})", "x": sw["x"], "y": sw["responses"][resp],
                               "current": float(point.get(f.key, f.center))})
            rep.heading(f"Tek faktör taramaları — {ylabel}")
            rep.image(charts.sweep_grid(panels, ylabel, hline), 0.95)
        rep.note("Her grafikte yalnızca ilgili faktör değişir; diğerleri yukarıdaki ayarlarda sabittir. "
                 "Noktalı dikey çizgi mevcut değeri gösterir.")

        opt = sim.literature_optimum(settings, goals, overrides)
        rep.heading("Literatür modeline göre optimum")
        rep.lead("Başlangıç SO₂ hammadde özelliği olduğundan optimum her parti seviyesi için ayrı aranmıştır "
                      "(desirability, ızgara araması).")
        rep.table(_optimum_table(opt["optimum"], goals.so2_limit))

        params = sim.parameters(overrides).to_dict()
        if overrides:
            rep.heading("Değiştirilen model varsayımları")
            base = self._literature.calibrated_parameters().to_dict()
            rep.table(TableBlock(columns=["Parametre", "Varsayılan", "Kullanılan"],
                                 rows=[[k, tr(base[k], 4), tr(params[k], 4)] for k in overrides],
                                 col_widths=[2, 1, 1]))
        rep.heading("Model parametreleri")
        rows = []
        for g in PARAMETER_GROUPS:
            for name in g["params"]:
                rows.append([g["label"], g["source"], name, tr(params[name], 4)])
        rep.table(TableBlock(columns=["Grup", "Kaynak", "Parametre", "Değer"], rows=rows, col_widths=[2.2, 1.2, 2, 1]))
        rep.note(ASSUMPTION_NOTE)
        return render(rep)

