import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { api } from '../api/client.js'
import { ErrorNote, Section, SettingsBar } from '../components/common.jsx'
import { fmt, pct } from '../lib/format.js'
import { OptimumTable } from './SimulatorPage.jsx'

const FAMILY_COLORS = { 'Klasik RSM': 'var(--c1)', Optimal: 'var(--c2)', 'Uzay dolduran': 'var(--c3)' }

// Grafikte etiketler üst üste binmesin diye kısa kodlar
const shortName = (key) => ({ ccd_half: 'CCD½', ccd_full: 'CCD', bbd: 'BBD' }[key]
  ?? key.replace(/^d_opt_/, 'D').replace(/^i_opt_/, 'I').replace(/^lhs_/, 'LHS'))

const RESPONSE_LABELS = {
  so2_final: 'SO₂', drying_time: 'Kurutma s.', total_time: 'Toplam s.', color_L: 'L*', color_dE: 'ΔE',
}

export default function DesignComparisonPage({ meta, settings, setSettings, goals, setGoals, overrides }) {
  const [catalog, setCatalog] = useState([])
  const [selected, setSelected] = useState([])
  const [scenarios, setScenarios] = useState(meta.scenarios.map((s) => s.key))
  const [nReps, setNReps] = useState(200)
  const [logTransform, setLogTransform] = useState(true)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.designs().then((c) => {
      setCatalog(c)
      setSelected(c.map((d) => d.key))
    }).catch((e) => setError(e.message))
  }, [])

  const byKey = useMemo(() => Object.fromEntries(catalog.map((d) => [d.key, d])), [catalog])
  const families = useMemo(() => [...new Set(catalog.map((d) => d.family))], [catalog])

  const toggle = (list, setList, key) =>
    setList(list.includes(key) ? list.filter((k) => k !== key) : [...list, key])

  const run = () => {
    setLoading(true)
    setError(null)
    const t0 = performance.now()
    api.evaluate({ designs: selected, scenarios, n_reps: nReps, log_transform: logTransform, settings, goals, overrides })
      .then((r) => { setResult(r); setElapsed((performance.now() - t0) / 1000) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  const estimate = Math.max(1, Math.round((selected.length * scenarios.length * nReps) / 450))

  return (
    <div className="stack">
      <Section title="Yöntem"
        subtitle="Desenler laboratuvarda değil, literatür tabanlı sanal kayısı üzerinde karşılaştırılır.">
        <ol className="method">
          <li><strong>İstatistik ölçütler</strong> (yanıt gerektirmez): D-/G-verimliliği, ortalama tahmin varyansı, VIF, saf hata serbestlik derecesi.</li>
          <li><strong>Monte Carlo:</strong> her desen sanal prosesle yüzlerce kez “uygulanır”, ölçüm hatası eklenir, her yanıta ikinci dereceden RSM modeli uydurulur.</li>
          <li><strong>Optimum kaybı:</strong> modelin önerdiği ayarın <em>gerçek</em> istenirliği, gerçek optimumla kıyaslanır (0 = mükemmel). Her başlangıç SO₂ seviyesi için ayrı hesaplanır.</li>
          <li><strong>Sağlamlık:</strong> literatür modeli belirsiz olduğu için test farklı “gerçek” senaryolarda tekrarlanır.</li>
          <li><strong>Karar:</strong> en iyi ortalama kayba %25 (en az 0,005) yakınlıktaki desenler arasından en az deneyli olan önerilir.</li>
        </ol>
      </Section>

      <Section title="Karşılaştırma ayarları"
        actions={<button className="btn" onClick={run} disabled={loading || !selected.length || !scenarios.length}>
          {loading ? 'Çalışıyor…' : 'Karşılaştırmayı çalıştır'}</button>}>
        <SettingsBar settings={settings} setSettings={setSettings} />
        <div className="cols-3">
          <div>
            <h3>Desenler</h3>
            {families.map((fam) => (
              <div key={fam} className="check-group">
                <div className="muted small">{fam}</div>
                {catalog.filter((d) => d.family === fam).map((d) => (
                  <label key={d.key} className="check" title={d.description}>
                    <input type="checkbox" checked={selected.includes(d.key)} onChange={() => toggle(selected, setSelected, d.key)} />
                    {d.label} <span className="muted">· {d.n_runs} deney</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
          <div>
            <h3>Senaryolar</h3>
            {meta.scenarios.map((s) => (
              <label key={s.key} className="check" title={s.description}>
                <input type="checkbox" checked={scenarios.includes(s.key)} onChange={() => toggle(scenarios, setScenarios, s.key)} />
                <span>{s.label}<br /><span className="muted small">{s.description}</span></span>
              </label>
            ))}
          </div>
          <div>
            <h3>Hedefler ve hesap</h3>
            <div className="form-grid">
              <label>SO₂ limiti (ppm)
                <input type="number" step={50} value={goals.so2_limit}
                  onChange={(e) => setGoals({ ...goals, so2_limit: Number(e.target.value) })} />
              </label>
              <label>Ağırlık: SO₂
                <input type="number" min={0.1} step={0.5} value={goals.w_so2}
                  onChange={(e) => setGoals({ ...goals, w_so2: Number(e.target.value) })} />
              </label>
              <label>Ağırlık: toplam süre
                <input type="number" min={0.1} step={0.5} value={goals.w_time}
                  onChange={(e) => setGoals({ ...goals, w_time: Number(e.target.value) })} />
              </label>
              <label>Ağırlık: L*
                <input type="number" min={0.1} step={0.5} value={goals.w_L}
                  onChange={(e) => setGoals({ ...goals, w_L: Number(e.target.value) })} />
              </label>
              <label>Ağırlık: ΔE
                <input type="number" min={0.1} step={0.5} value={goals.w_dE}
                  onChange={(e) => setGoals({ ...goals, w_dE: Number(e.target.value) })} />
              </label>
              <label style={{ gridColumn: '1 / -1' }}>
                <span>Monte Carlo tekrarı <span className="small">(her desen, ölçüm hatası eklenerek sanal laboratuvarda bu kadar kez denenir; arttıkça sonuç kararlılaşır, hesap uzar)</span></span>
                <select value={nReps} onChange={(e) => setNReps(Number(e.target.value))}>
                  {[50, 100, 200, 500].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
            </div>
            <label className="check">
              <input type="checkbox" checked={logTransform} onChange={(e) => setLogTransform(e.target.checked)} />
              SO₂ ve süreleri log dönüşümüyle modelle
            </label>
            <p className="muted small">Tahmini süre: ~{estimate} sn</p>
          </div>
        </div>
      </Section>

      <ErrorNote error={error} />
      {result && <Results result={result} byKey={byKey} elapsed={elapsed} meta={meta} goals={goals} />}
    </div>
  )
}

function Results({ result, byKey, elapsed, meta, goals }) {
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState(null)
  const exportPdf = () => {
    setPdfLoading(true)
    setPdfError(null)
    api.comparisonPdf(result).catch((e) => setPdfError(e.message)).finally(() => setPdfLoading(false))
  }
  const rec = result.recommendation
  const recDesign = byKey[rec.design]
  const label = (k) => byKey[k]?.label ?? k
  const points = result.ranking.map((r) => ({
    n: r.n_runs, regret: r.regret_mean, name: shortName(r.design), full: label(r.design), family: byKey[r.design]?.family,
  }))
  const maxRegret = Math.max(...result.scenarios.flatMap((s) => Object.values(s.results).map((x) => x.regret_mean)))

  return (
    <>
      <section className="card recommendation">
        <div className="rec-head">
          <div className="rec-label">Önerilen desen</div>
          <button className="btn" onClick={exportPdf} disabled={pdfLoading}>
            {pdfLoading ? 'PDF hazırlanıyor…' : 'PDF raporu indir'}</button>
        </div>
        <div className="rec-title">{recDesign?.label} <span className="muted">· {recDesign?.n_runs} deney</span></div>
        <p>
          En iyi ortalama optimum kaybı {fmt(rec.best_regret, 4)}. Tolerans ({fmt(rec.tolerance, 4)}) içinde kalan desenler:{' '}
          {rec.eligible.map(label).join(', ')}. Bunlar arasında en az deneyli olan önerildi.
        </p>
        <p className="muted small">
          {result.n_reps} tekrar · {result.scenarios.length} senaryo · {result.settings.n_applications} uygulama · hedef nem %{result.settings.target_moisture}
          {elapsed && ` · ${fmt(elapsed, 1)} sn`}
        </p>
        <ErrorNote error={pdfError} />
      </section>

      <Section title="Deney sayısı – optimum kaybı"
        subtitle="Sol alta yakın = az deneyle iyi optimum. Eğrinin dirsek yaptığı yer en verimli bölgedir. D/I = D-/I-optimal, LHS = Latin hiperküp, CCD½ = yarım faktöriyel CCD.">
        <div className="chart">
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 20, right: 30, bottom: 30, left: 10 }}>
              <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="n" name="Deney sayısı" stroke="var(--muted)" domain={[25, 'auto']}
                label={{ value: 'Deney sayısı', position: 'insideBottom', offset: -15, fill: 'var(--muted)' }} />
              <YAxis type="number" dataKey="regret" name="Optimum kaybı" stroke="var(--muted)" tickFormatter={(v) => fmt(v, 3)} />
              <ZAxis range={[90, 90]} />
              <Tooltip formatter={(v, n) => [n === 'Optimum kaybı' ? fmt(v, 4) : v, n]}
                labelFormatter={(_, items) => items?.[0]?.payload?.full ?? ''}
                contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }} />
              {Object.entries(FAMILY_COLORS).map(([fam, color]) => (
                <Scatter key={fam} name={fam} data={points.filter((p) => p.family === fam)} fill={color}>
                  <LabelList dataKey="name" position="top" style={{ fontSize: 11, fill: 'var(--text)' }} />
                </Scatter>
              ))}
            </ScatterChart>
          </ResponsiveContainer>
          <div className="legend">
            {Object.entries(FAMILY_COLORS).map(([fam, color]) => (
              <span key={fam}><i style={{ background: color }} />{fam}</span>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Sıralama ve istatistik ölçütler"
        subtitle="Kayıp ve başarı oranları tüm senaryoların ortalamasıdır. 'Yanlış uygun': model SO₂ limitinin altında der, gerçekte üstündedir.">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Desen</th><th>Deney</th><th>Ort. kayıp</th><th>En kötü senaryo</th><th>Başarı</th><th>Yanlış uygun</th>
                <th>D-verim.</th><th>G-verim.</th><th>Ort. tahmin var.</th><th>Maks. VIF</th><th>Saf hata sd</th>
              </tr>
            </thead>
            <tbody>
              {result.ranking.map((r) => {
                const c = result.criteria[r.design]
                return (
                  <tr key={r.design} className={r.design === rec.design ? 'highlight' : ''}>
                    <td>{label(r.design)}</td>
                    <td>{r.n_runs}</td>
                    <td><strong>{fmt(r.regret_mean, 4)}</strong></td>
                    <td>{fmt(r.regret_worst, 4)}</td>
                    <td>{pct(r.success_rate)}</td>
                    <td className={r.false_feasible_rate > 0.2 ? 'bad-text' : ''}>{pct(r.false_feasible_rate)}</td>
                    <td>{fmt(c.d_efficiency, 1)}</td>
                    <td>{fmt(c.g_efficiency, 1)}</td>
                    <td>{fmt(c.avg_pred_variance, 3)}</td>
                    <td className={c.vif_max > 10 ? 'bad-text' : ''}>{fmt(c.vif_max, 2)}</td>
                    <td className={c.df_pure_error === 0 ? 'bad-text' : ''}>{c.df_pure_error}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Başarı: optimum kaybı ≤ 0,02 olan tekrar oranı. Saf hata sd = 0 olan desenlerde (tekrar noktası yok) uyum eksikliği testi yapılamaz;
          uygulamada 3–4 merkez tekrarı eklenmesi önerilir.
        </p>
      </Section>

      <Section title="Senaryo × desen optimum kaybı" subtitle="Koyu hücre = daha büyük kayıp.">
        <div className="table-wrap">
          <table className="heat">
            <thead>
              <tr><th>Desen</th>{result.scenarios.map((s) => <th key={s.scenario.key}>{s.scenario.label}</th>)}</tr>
            </thead>
            <tbody>
              {result.ranking.map((r) => (
                <tr key={r.design}>
                  <td>{label(r.design)}</td>
                  {result.scenarios.map((s) => {
                    const v = s.results[r.design].regret_mean
                    return <td key={s.scenario.key} style={{ '--heat': Math.min(1, v / maxRegret) }}>{fmt(v, 4)}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {result.scenarios.map((s) => (
        <details key={s.scenario.key} className="card">
          <summary><strong>{s.scenario.label}</strong> — gerçek optimum ve yanıt bazında tahmin hatası</summary>
          <p className="muted">{s.scenario.description}</p>
          <OptimumTable meta={meta} optimum={s.optimum} goals={goals} />
          <h3>Normalleştirilmiş tahmin hatası (RMSE / yanıt SD)</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Desen</th>{Object.values(RESPONSE_LABELS).map((l) => <th key={l}>{l}</th>)}<th>SO₂ sınıflandırma doğruluğu</th></tr>
              </thead>
              <tbody>
                {result.ranking.map((r) => {
                  const res = s.results[r.design]
                  return (
                    <tr key={r.design}>
                      <td>{label(r.design)}</td>
                      {Object.keys(RESPONSE_LABELS).map((k) => <td key={k}>{fmt(res.nrmse[k], 3)}</td>)}
                      <td>{pct(res.so2_classification_accuracy, 1)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </>
  )
}
