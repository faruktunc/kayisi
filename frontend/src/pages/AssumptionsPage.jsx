import { Section } from '../components/common.jsx'

const DESCRIPTIONS = {
  so2_ln_k0: 'Referans hız sabitinin logaritması (C=%1, 25 °C, SO₂₀=4500 ppm)',
  so2_a_conc: 'H₂O₂ konsantrasyonu üssü',
  so2_b_temp: 'Sıcaklık katsayısı (1/°C)',
  so2_c_conc_temp: 'ln C × sıcaklık etkileşimi',
  so2_m_initial: 'Başlangıç SO₂ etkisi',
  moisture_in: 'Gelen kuru kayısı nemi (% yaş baz)',
  moisture_saturation: 'Çözeltide ulaşılabilecek üst nem (%)',
  uptake_tau: 'Su alımı zaman sabiti, 25 °C (dk)',
  uptake_temp_coef: 'Su alımının sıcaklık katsayısı (1/°C)',
  dry_k_ref: 'Page sabiti, 45 °C ve 480 mmHg (1/hⁿ)',
  dry_n: 'Page üssü',
  dry_ea: 'Kurutma aktivasyon enerjisi (J/mol)',
  dry_pressure_exp: 'Basınç etkisi üssü β: k ∝ (480/P)^β',
  moisture_equilibrium: 'Denge nemi (% yaş baz)',
  so2_dry_loss_ref: 'Kurutmada ısıl SO₂ kaybı, 45 °C (1/h)',
  so2_dry_loss_temp: 'SO₂ kaybının sıcaklık katsayısı (1/°C)',
  so2_dry_loss_pressure_exp: 'SO₂ kaybının basınç üssü',
  color_ref_L: 'Referans L* (ticari kükürtlü)',
  color_ref_a: 'Referans a*',
  color_ref_b: 'Referans b*',
  browning_k_ref: 'Esmerleşme hızı, 45 °C (L*/h)',
  browning_temp_coef: 'Esmerleşmenin sıcaklık katsayısı (1/°C)',
  so2_protection_scale: 'SO₂ koruma ölçeği (ppm)',
  so2_protection_gain: 'Korumasız ek esmerleşme çarpanı',
  h2o2_bleach_b: 'H₂O₂ ağartma etkisi (b*, %·10 dk başına)',
  a_per_L: '|ΔL*| başına a* artışı',
  b_per_L: '|ΔL*| başına b* azalışı',
  noise_so2_rel: 'SO₂ ölçüm hatası (bağıl SD)',
  noise_time_rel: 'Kurutma süresi hatası (bağıl SD)',
  noise_L: 'L* ölçüm SD',
  noise_a: 'a* ölçüm SD',
  noise_b: 'b* ölçüm SD',
}

export default function AssumptionsPage({ meta, overrides, setOverrides }) {
  const base = meta.parameters
  const set = (name, raw) => {
    const value = Number(raw)
    const next = { ...overrides }
    if (raw === '' || Number.isNaN(value) || value === base[name]) delete next[name]
    else next[name] = value
    setOverrides(next)
  }

  return (
    <div className="stack">
      <Section title="Model varsayımları"
        subtitle="Değiştirilen değerler simülatör, optimum ve desen karşılaştırmasında kullanılır (senaryo değerlerinin üzerine yazılır)."
        actions={<button className="btn ghost" onClick={() => setOverrides({})} disabled={!Object.keys(overrides).length}>Tümünü sıfırla</button>}>
        <div className="param-groups">
          {meta.parameter_groups.map((g) => (
            <div key={g.key} className="param-group">
              <h3>{g.label} <span className={`source ${g.source === 'literatür' ? 'lit' : 'assume'}`}>{g.source}</span></h3>
              {g.params.map((name) => {
                const changed = name in overrides
                return (
                  <label key={name} className={changed ? 'param changed' : 'param'}>
                    <span>{DESCRIPTIONS[name] ?? name}<br /><code className="muted small">{name}</code></span>
                    <input type="number" step="any" value={changed ? overrides[name] : +base[name].toPrecision(4)}
                      onChange={(e) => set(name, e.target.value)} />
                  </label>
                )
              })}
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
