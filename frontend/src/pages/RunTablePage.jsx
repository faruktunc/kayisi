import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { ErrorNote, Section } from '../components/common.jsx'
import { fmt } from '../lib/format.js'

export default function RunTablePage({ meta }) {
  const [catalog, setCatalog] = useState([])
  const [key, setKey] = useState('ccd_half')
  const [seed, setSeed] = useState(1)
  const [data, setData] = useState(null)
  // Föyde sabit koşullar; boş bırakılan alan föyde 'kararlaştırılacak' olarak basılır
  const [conditions, setConditions] = useState({ n_applications: '', target_moisture: '', pressure_mode: '' })
  const setCond = (k, v) => setConditions({ ...conditions, [k]: v })
  const [error, setError] = useState(null)

  useEffect(() => { api.designs().then(setCatalog).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    api.design(key, seed).then((d) => { setData(d); setError(null) }).catch((e) => setError(e.message))
  }, [key, seed])

  const c = data?.criteria
  return (
    <div className="stack">
      <Section title="Laboratuvar deney tablosu"
        subtitle="Gerçek birimlerde, rastgele sırada. Yanıt sütunları boş gelir; deneyler yapıldıkça doldurulur."
        actions={
          <div className="inline-controls">
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {catalog.map((d) => <option key={d.key} value={d.key}>{d.label} ({d.n_runs})</option>)}
            </select>
            <label className="inline">Sıra tohumu
              <input type="number" value={seed} min={0} onChange={(e) => setSeed(Number(e.target.value))} style={{ width: 70 }} />
            </label>
            <a className="btn ghost" href={api.designCsvUrl(key, seed)}>CSV indir</a>
            <a className="btn" href={api.designPdfUrl(key, seed, conditions)}>PDF föy indir</a>
          </div>
        }>
        <ErrorNote error={error} />
        <div className="settings-bar">
          <strong className="small">Föydeki sabit koşullar</strong>
          <label>
            H₂O₂ uygulama sayısı
            <select value={conditions.n_applications} onChange={(e) => setCond('n_applications', e.target.value)}>
              <option value="">Kararlaştırılacak</option>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label>
            Hedef nem (% yaş baz)
            <input type="number" min={18} max={28} step={0.5} placeholder="boş" value={conditions.target_moisture}
              onChange={(e) => setCond('target_moisture', e.target.value)} />
          </label>
          <label>
            Vakum basıncı tanımı
            <select value={conditions.pressure_mode} onChange={(e) => setCond('pressure_mode', e.target.value)}>
              <option value="">Kararlaştırılacak</option>
              <option value="absolute">Mutlak basınç</option>
              <option value="gauge">Vakum göstergesi</option>
            </select>
          </label>
          <span className="muted small">Boş alanlar föyde doldurulacak şekilde basılır.</span>
        </div>
        {data && (
          <>
            <p className="muted">{data.design.description}</p>
            {c && (
              <div className="chips">
                <span>{c.n_runs} deney</span>
                <span>{c.n_distinct} farklı nokta</span>
                <span>{c.n_center} merkez noktası</span>
                <span>Seviye sayısı: {c.levels_per_factor.join(' / ')}</span>
                <span>Uyum eksikliği sd: {c.df_lack_of_fit}</span>
                <span className={c.df_pure_error === 0 ? 'chip-bad' : ''}>Saf hata sd: {c.df_pure_error}</span>
                {c.estimable && <span>D-verim. {fmt(c.d_efficiency, 1)}</span>}
                {c.estimable && <span>Ort. tahmin var. {fmt(c.avg_pred_variance, 3)}</span>}
              </div>
            )}
            <div className="table-wrap tall">
              <table>
                <thead>
                  <tr>
                    <th>Sıra</th><th>Desen no</th>
                    {meta.factors.map((f) => <th key={f.key}>{f.label} <span className="muted">({f.unit})</span></th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.run_order}>
                      <td>{r.run_order}</td>
                      <td className="muted">{r.standard_order}</td>
                      {meta.factors.map((f) => <td key={f.key}>{fmt(r.factors[f.key], f.step < 0.1 ? 2 : f.step < 1 ? 1 : 0)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>
    </div>
  )
}
