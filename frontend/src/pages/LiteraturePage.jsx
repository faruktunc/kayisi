import { useEffect, useState } from 'react'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, ReferenceLine } from 'recharts'
import { api } from '../api/client.js'
import { ErrorNote, Section, Stat } from '../components/common.jsx'
import { fmt } from '../lib/format.js'

const GROUP_COLORS = { ozkan: 'var(--c1)', 'ugur-H': 'var(--c2)', 'ugur-K': 'var(--c3)' }
const GROUP_LABELS = { ozkan: 'Özkan & Cemeroğlu', 'ugur-H': 'Uğur & Erdoğan (H serisi)', 'ugur-K': 'Uğur & Erdoğan (K serisi)' }

export default function LiteraturePage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { api.literature().then(setData).catch((e) => setError(e.message)) }, [])
  if (error) return <ErrorNote error={error} />
  if (!data) return <p className="muted">Yükleniyor…</p>
  const f = data.fit
  const groups = Object.keys(GROUP_COLORS)

  return (
    <div className="stack">
      <Section title="SO₂ kinetiği kalibrasyonu"
        subtitle="SO₂(t) = SO₂₀·exp(−k·t),  ln k = ln k₀ + a·ln C + b·(T − 25) − m·ln(SO₂₀ / 4500) + çalışma etkisi">
        <div className="stats">
          <Stat label="ln k₀" value={fmt(f.ln_k0, 3)} hint={`k₀ = ${fmt(Math.exp(f.ln_k0), 4)} 1/dk`} />
          <Stat label="a (konsantrasyon üssü)" value={fmt(f.a_conc, 3)} />
          <Stat label="b (sıcaklık, 1/°C)" value={fmt(f.b_temp, 4)} />
          <Stat label="m (başlangıç SO₂ etkisi)" value={fmt(f.m_initial, 2)}
            hint="Yüksek başlangıç SO₂ → oransal azalma düşük" />
          <Stat label="R² (SO₂)" value={fmt(f.r2_so2, 3)} />
          <Stat label="R² (ln k)" value={fmt(f.r2_ln_k, 3)} />
          <Stat label="RMSE" value={fmt(f.rmse_so2, 0)} unit="ppm" />
          <Stat label="Gözlem" value={f.n_obs} />
        </div>
        <p className="muted small">
          Çalışma/çeşit etkileri (ln k): {Object.entries(f.group_effects).map(([g, v]) => `${GROUP_LABELS[g] ?? g}: ${fmt(v, 2)}`).join(' · ')}.
          Simülatör ortalama grubu kullanır. Sıcaklık etkisi literatürde zayıf ve tutarsızdır (b küçük);
          başlangıç SO₂ düzeyi en güçlü belirleyicidir.
        </p>
      </Section>

      <Section title="Gözlenen ve tahmin edilen SO₂" subtitle="Köşegene yakın noktalar iyi uyumu gösterir.">
        <div className="chart">
          <ResponsiveContainer width="100%" height={380}>
            <ScatterChart margin={{ top: 10, right: 30, bottom: 30, left: 20 }}>
              <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="so2" name="Gözlenen" domain={[500, 6000]} stroke="var(--muted)"
                label={{ value: 'Gözlenen SO₂ (ppm)', position: 'insideBottom', offset: -15, fill: 'var(--muted)' }} />
              <YAxis type="number" dataKey="predicted" name="Tahmin" domain={[500, 6000]} stroke="var(--muted)"
                label={{ value: 'Tahmin (ppm)', angle: -90, position: 'insideLeft', fill: 'var(--muted)' }} />
              <ZAxis range={[50, 50]} />
              <ReferenceLine segment={[{ x: 500, y: 500 }, { x: 6000, y: 6000 }]} stroke="var(--muted)" strokeDasharray="4 4" />
              <Tooltip formatter={(v) => fmt(v, 0)} contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }} />
              {groups.map((g) => (
                <Scatter key={g} name={GROUP_LABELS[g]} data={data.observations.filter((o) => o.group === g)} fill={GROUP_COLORS[g]} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
          <div className="legend">
            {groups.map((g) => <span key={g}><i style={{ background: GROUP_COLORS[g] }} />{GROUP_LABELS[g]}</span>)}
          </div>
        </div>
      </Section>

      <Section title="Kaynaklar ve veri">
        <ul>{data.studies.map((s) => <li key={s.key}>{s.citation}</li>)}</ul>
        <div className="table-wrap tall">
          <table>
            <thead>
              <tr><th>Örnek</th><th>Grup</th><th>H₂O₂ (%)</th><th>Sıcaklık (°C)</th><th>Süre (dk)</th><th>Başlangıç SO₂</th><th>Gözlenen</th><th>Tahmin</th></tr>
            </thead>
            <tbody>
              {data.observations.map((o) => (
                <tr key={o.sample}>
                  <td>{o.sample}</td><td>{GROUP_LABELS[o.group]}</td><td>{fmt(o.h2o2_conc, 1)}</td><td>{o.temp}</td><td>{o.time}</td>
                  <td>{fmt(o.so2_initial, 0)}</td><td>{fmt(o.so2, 0)}{o.sd ? ` ± ${o.sd}` : ''}</td><td>{fmt(o.predicted, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}
