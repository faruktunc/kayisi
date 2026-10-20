"""Sanal kayısı: ardışık H₂O₂ uygulaması + vakumlu kurutma proses modeli.

Tüm hesaplar numpy ile vektörleştirilmiştir; girdi (n, 6) gerçek birim
matrisidir (sütun sırası shared.factors.FACTORS ile aynı).

Modelin parçaları:
  1. H₂O₂ aşaması (her uygulama için)
       - SO₂: birinci dereceden kinetik, k literatürden kalibre edilir
       - Nem: çözeltiden su alımı, doygunluk nemine üstel yaklaşım
  2. Vakumlu kurutma (hedef neme kadar)
       - Nem: Page modeli MR = exp(-k·tⁿ), k Arrhenius × basınç etkisi
       - SO₂: ısıl kayıp (birinci derece) + su kaybından gelen derişme
  3. Renk: esmerleşme kinetiği (sıcaklık × süre), kalan SO₂ koruyucu etki
       yapar; referans = ticari kükürtlü kuru kayısı rengi

1. aşamanın SO₂ kısmı literatüre dayanır; nem ve renk kısmı bu ürüne ait
veri olmadığından VARSAYIMDIR ve parametreleri değiştirilebilir.
"""
from dataclasses import asdict, dataclass, field, fields, replace

import numpy as np

R_GAS = 8.314
DRY_T_REF = 45.0
DRY_P_REF = 480.0


@dataclass(frozen=True)
class ProcessSettings:
    """Desenin faktörü olmayan, proses boyunca sabit tutulan ayarlar."""
    n_applications: int = 1
    target_moisture: float = 22.0  # % yaş baz, kurutma bu neme inince biter

    def __post_init__(self):
        if not 1 <= self.n_applications <= 5:
            raise ValueError("Uygulama sayısı 1 ile 5 arasında olmalı")
        if not 10 <= self.target_moisture <= 35:
            raise ValueError("Hedef nem %10 ile %35 arasında olmalı")


@dataclass(frozen=True)
class ModelParameters:
    # --- H₂O₂ aşaması: SO₂ kinetiği (literatürden kalibre edilir) ---
    so2_ln_k0: float = -3.76
    so2_a_conc: float = 0.59
    so2_b_temp: float = 0.0117
    so2_c_conc_temp: float = 0.0
    so2_m_initial: float = 2.18

    # --- H₂O₂ aşaması: su alımı (varsayım) ---
    moisture_in: float = 24.0          # % yaş baz, gelen kuru kayısı
    moisture_saturation: float = 43.0  # % yaş baz, çözeltide ulaşılabilecek üst nem
    uptake_tau: float = 40.0           # dk, 25 °C'de su alımı zaman sabiti
    uptake_temp_coef: float = 0.03     # 1/°C, sıcaklık arttıkça su alımı hızlanır

    # --- Vakumlu kurutma (varsayım) ---
    dry_k_ref: float = 0.14            # 1/hⁿ, 45 °C ve 480 mmHg'de Page sabiti
    dry_n: float = 0.9                 # Page üssü
    dry_ea: float = 30000.0            # J/mol, kurutma aktivasyon enerjisi
    dry_pressure_exp: float = 1.0      # k ∝ (P_ref / P)^β
    moisture_equilibrium: float = 7.0  # % yaş baz, denge nemi

    # --- Kurutmada SO₂ kaybı (varsayım) ---
    so2_dry_loss_ref: float = 0.02     # 1/h, 45 °C'de ısıl SO₂ kaybı
    so2_dry_loss_temp: float = 0.06    # 1/°C
    so2_dry_loss_pressure_exp: float = 0.5

    # --- Renk (varsayım) ---
    color_ref_L: float = 52.0          # ticari kükürtlü ürün referansı
    color_ref_a: float = 16.0
    color_ref_b: float = 42.0
    browning_k_ref: float = 0.5        # L*/h, 45 °C'de korumasız esmerleşme hızı
    browning_temp_coef: float = 0.07   # 1/°C
    so2_protection_scale: float = 2000.0  # ppm; SO₂ bu düzeyin altına indikçe koruma azalır
    so2_protection_gain: float = 3.0      # korumasız durumdaki ek esmerleşme çarpanı
    h2o2_bleach_b: float = 0.8         # H₂O₂'nin b* (sarılık) üzerindeki ağartma etkisi, %·10 dk başına
    a_per_L: float = 0.25              # esmerleşmede |ΔL*| başına a* artışı
    b_per_L: float = 0.6               # esmerleşmede |ΔL*| başına b* azalışı

    # --- Ölçüm hatası (simüle deneylerde) ---
    noise_so2_rel: float = 0.04
    noise_time_rel: float = 0.06
    noise_L: float = 1.0
    noise_a: float = 0.6
    noise_b: float = 1.0

    def with_overrides(self, overrides: dict | None) -> "ModelParameters":
        if not overrides:
            return self
        valid = {f.name for f in fields(self)}
        unknown = set(overrides) - valid
        if unknown:
            raise ValueError(f"Bilinmeyen model parametresi: {', '.join(sorted(unknown))}")
        return replace(self, **{k: float(v) for k, v in overrides.items()})

    def to_dict(self) -> dict:
        return asdict(self)


# Arayüzde gruplanmış parametre açıklamaları
PARAMETER_GROUPS = [
    {"key": "so2", "label": "H₂O₂ aşaması — SO₂ kinetiği", "source": "literatür",
     "params": ["so2_ln_k0", "so2_a_conc", "so2_b_temp", "so2_c_conc_temp", "so2_m_initial"]},
    {"key": "uptake", "label": "H₂O₂ aşaması — su alımı", "source": "varsayım",
     "params": ["moisture_in", "moisture_saturation", "uptake_tau", "uptake_temp_coef"]},
    {"key": "drying", "label": "Vakumlu kurutma", "source": "varsayım",
     "params": ["dry_k_ref", "dry_n", "dry_ea", "dry_pressure_exp", "moisture_equilibrium"]},
    {"key": "so2_dry", "label": "Kurutmada SO₂ kaybı", "source": "varsayım",
     "params": ["so2_dry_loss_ref", "so2_dry_loss_temp", "so2_dry_loss_pressure_exp"]},
    {"key": "color", "label": "Renk", "source": "varsayım",
     "params": ["color_ref_L", "color_ref_a", "color_ref_b", "browning_k_ref", "browning_temp_coef",
                "so2_protection_scale", "so2_protection_gain", "h2o2_bleach_b", "a_per_L", "b_per_L"]},
    {"key": "noise", "label": "Ölçüm hatası", "source": "literatür SD / varsayım",
     "params": ["noise_so2_rel", "noise_time_rel", "noise_L", "noise_a", "noise_b"]},
]

RESPONSES = (
    {"key": "so2_final", "label": "Nihai toplam SO₂", "unit": "ppm"},
    {"key": "drying_time", "label": "Kurutma süresi", "unit": "saat"},
    {"key": "total_time", "label": "Toplam işlem süresi", "unit": "saat"},
    {"key": "color_L", "label": "Renk L*", "unit": ""},
    {"key": "color_dE", "label": "Renk farkı ΔE", "unit": ""},
)
RESPONSE_KEYS = tuple(r["key"] for r in RESPONSES)


def _wb_to_db(w):
    w = np.asarray(w, dtype=float) / 100
    return w / (1 - w)


def _db_to_wb(x):
    return 100 * x / (1 + x)


@dataclass
class ProcessSimulator:
    params: ModelParameters = field(default_factory=ModelParameters)

    def so2_rate(self, conc, temp, so2_lot):
        """Hız sabiti (1/dk). Başlangıç SO₂ etkisi partinin özelliğidir (kükürdün
        bağlanma biçimi); ardışık uygulamalarda değişmez, aksi halde k kendini
        hızlandırıp SO₂'yi gerçek dışı biçimde sıfıra çeker."""
        p = self.params
        ln_c = np.log(conc)
        dt = temp - 25.0
        ln_k = (p.so2_ln_k0 + p.so2_a_conc * ln_c + p.so2_b_temp * dt
                + p.so2_c_conc_temp * ln_c * dt - p.so2_m_initial * np.log(so2_lot / 4500.0))
        return np.exp(ln_k)

    def run(self, natural: np.ndarray, settings: ProcessSettings) -> dict:
        """Gürültüsüz ('gerçek') proses yanıtları."""
        p = self.params
        X = np.atleast_2d(np.asarray(natural, dtype=float))
        s0, conc, t_dip, T_dip, T_dry, P = X.T

        # 1) Ardışık H₂O₂ uygulamaları
        so2 = s0.copy()
        x_db = np.full_like(s0, _wb_to_db(p.moisture_in))
        x_sat = _wb_to_db(p.moisture_saturation)
        tau = p.uptake_tau * np.exp(-p.uptake_temp_coef * (T_dip - 25.0))
        k_so2 = self.so2_rate(conc, T_dip, s0)
        for _ in range(settings.n_applications):
            so2 = so2 * np.exp(-k_so2 * t_dip)
            x_db = x_sat - (x_sat - x_db) * np.exp(-t_dip / tau)
        so2_after_dip = so2
        moisture_after_dip = _db_to_wb(x_db)

        # 2) Vakumlu kurutma: hedef neme kadar (Page modeli tersinden süre)
        x_eq = _wb_to_db(p.moisture_equilibrium)
        x_target = _wb_to_db(settings.target_moisture)
        T_k = T_dry + 273.15
        k_dry = (p.dry_k_ref * np.exp(p.dry_ea / R_GAS * (1 / (DRY_T_REF + 273.15) - 1 / T_k))
                 * (DRY_P_REF / P) ** p.dry_pressure_exp)
        needs_drying = x_db > x_target
        mr = np.clip((x_target - x_eq) / np.maximum(x_db - x_eq, 1e-9), 1e-9, 1.0)
        drying_time = np.where(needs_drying, (-np.log(mr) / k_dry) ** (1 / p.dry_n), 0.0)
        moisture_final = np.where(needs_drying, settings.target_moisture, moisture_after_dip)

        k_loss = (p.so2_dry_loss_ref * np.exp(p.so2_dry_loss_temp * (T_dry - DRY_T_REF))
                  * (DRY_P_REF / P) ** p.so2_dry_loss_pressure_exp)
        # ppm yaş baz: su kaybı kuru maddeyi, dolayısıyla SO₂ derişimini artırır
        concentration = (1 - moisture_final / 100) / (1 - moisture_after_dip / 100)
        so2_final = so2_after_dip * np.exp(-k_loss * drying_time) * concentration

        # 3) Renk: kurutma boyunca ortalama SO₂ ile korunma
        so2_mean = 0.5 * (so2_after_dip + so2_final)
        protection_loss = np.exp(-so2_mean / p.so2_protection_scale)
        rate = p.browning_k_ref * np.exp(p.browning_temp_coef * (T_dry - DRY_T_REF)) * (1 + p.so2_protection_gain * protection_loss)
        dL = -rate * drying_time
        L = np.maximum(p.color_ref_L + dL, 0.0)
        a = p.color_ref_a + p.a_per_L * np.abs(dL)
        b = (p.color_ref_b - p.b_per_L * np.abs(dL)
             - p.h2o2_bleach_b * conc * settings.n_applications * t_dip / 10.0)
        dE = np.sqrt((L - p.color_ref_L) ** 2 + (a - p.color_ref_a) ** 2 + (b - p.color_ref_b) ** 2)

        dip_time_h = settings.n_applications * t_dip / 60.0
        return {
            "so2_after_dip": so2_after_dip,
            "moisture_after_dip": moisture_after_dip,
            "so2_final": so2_final,
            "moisture_final": moisture_final,
            "drying_time": drying_time,
            "total_time": dip_time_h + drying_time,
            "color_L": L,
            "color_a": a,
            "color_b": b,
            "color_dE": dE,
        }

    def run_noisy(self, natural: np.ndarray, settings: ProcessSettings, rng: np.random.Generator,
                  noise_scale: float = 1.0) -> dict:
        """Laboratuvar ölçüm hatası eklenmiş yanıtlar (sanal deney)."""
        p = self.params
        true = self.run(natural, settings)
        n = true["so2_final"].shape[0]
        g = lambda sd: rng.normal(0.0, sd * noise_scale, n)
        dip_time_h = true["total_time"] - true["drying_time"]
        drying = true["drying_time"] * np.exp(g(p.noise_time_rel))
        L = true["color_L"] + g(p.noise_L)
        a = true["color_a"] + g(p.noise_a)
        b = true["color_b"] + g(p.noise_b)
        return {
            **true,
            "so2_final": true["so2_final"] * np.exp(g(p.noise_so2_rel)),
            "drying_time": drying,
            "total_time": dip_time_h + drying,
            "color_L": L,
            "color_a": a,
            "color_b": b,
            "color_dE": np.sqrt((L - p.color_ref_L) ** 2 + (a - p.color_ref_a) ** 2 + (b - p.color_ref_b) ** 2),
        }
