"""Sağlamlık senaryoları: 'gerçek' proses literatür modelinden farklıysa
desen seçimi değişiyor mu? Her senaryo, temel parametrelerin üzerine
yazılan değerler ve bir gürültü çarpanıdır."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    description: str
    overrides: dict = field(default_factory=dict)
    noise_scale: float = 1.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "overrides": self.overrides,
            "noise_scale": self.noise_scale,
        }


SCENARIOS: dict[str, Scenario] = {s.key: s for s in (
    Scenario("base", "Temel (literatür)", "Literatürden kalibre edilen SO₂ kinetiği ve varsayılan kurutma/renk parametreleri."),
    Scenario("strong_interaction", "Güçlü H₂O₂ × sıcaklık etkileşimi",
             "Konsantrasyonun etkisi sıcaklıkla belirgin biçimde artıyor.",
             {"so2_c_conc_temp": 0.08}),
    Scenario("weak_vacuum", "Zayıf vakum etkisi",
             "Basıncın kurutma hızına etkisi beklenenden çok daha az.",
             {"dry_pressure_exp": 0.2, "so2_dry_loss_pressure_exp": 0.1}),
    Scenario("color_sensitive", "Renk SO₂'ye çok duyarlı",
             "SO₂ azaldıkça esmerleşme çok daha hızlı başlıyor.",
             {"so2_protection_gain": 8.0, "so2_protection_scale": 2500.0, "browning_temp_coef": 0.09}),
    Scenario("high_noise", "Yüksek ölçüm hatası",
             "Laboratuvar ölçüm hataları temel senaryonun iki katı.",
             noise_scale=2.0),
)}
