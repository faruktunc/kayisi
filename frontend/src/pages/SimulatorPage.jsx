import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client.js'
import { ErrorNote, FactorSlider, Section, SettingsBar, Stat } from '../components/common.jsx'
import { labToHex } from '../lib/color.js'
import { fmt, hoursToText } from '../lib/format.js'

const SWEEP_RESPONSES = [
  { key: 'so2_final', label: 'Nihai SO₂ (ppm)', digits: 0 },
  { key: 'drying_time', label: 'Kurutma süresi (saat)', digits: 2 },
  { key: 'total_time', label: 'Toplam süre (saat)', digits: 2 },
  { key: 'color_L', label: 'L*', digits: 1 },
  { key: 'color_dE', label: 'ΔE', digits: 1 },
  { key: 'moisture_after_dip', label: 'H₂O₂ sonrası nem (%)', digits: 1 },
]

function useDebounced(value, delay = 150) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}

export default function SimulatorPage({ meta, settings, setSettings, goals, overrides, point, setPoint }) {
  const [result, setResult] = useState(null)
  const [sweepFactor, setSweepFactor] = useState('h2o2_time')
  const [sweepResponse, setSweepResponse] = useState('so2_final')
  const [sweep, setSweep] = useState(null)
  const [optimum, setOptimum] = useState(null)
  const [optLoading, setOptLoading] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [error, setError] = useState(null)

  const request = useDebounced({ point, settings, overrides, goals })

  useEffect(() => {
    api.simulate(request).then(setResult).then(() => setError(null)).catch((e) => setError(e.message))
  }, [request])

  useEffect(() => {
    api.sweep({ ...request, factor: sweepFactor }).then(setSweep).catch((e) => setError(e.message))
  }, [request, sweepFactor])

  useEffect(() => setOptimum(null), [settings, overrides, goals])

  const findOptimum = () => {
    setOptLoading(true)
    api.optimum({ settings, goals, overrides })
      .then(setOptimum)
      .catch((e) => setError(e.message))
      .finally(() => setOptLoading(false))
  }

  const exportPdf = () => {
    setPdfLoading(true)
    api.simulationPdf({ point, settings, goals, overrides })
      .catch((e) => setError(e.message))
      .finally(() => setPdfLoading(false))
  }

  const factor = meta.factors.find((f) => f.key === sweepFactor)
  const respMeta = SWEEP_RESPONSES.find((r) => r.key === sweepResponse)
  const chartData = sweep
    ? sweep.x.map((x, i) => ({ x, y: sweep.responses[sweepResponse][i] }))
    : []
  const p = { ...meta.parameters, ...overrides }
  const refHex = labToHex(p.color_ref_L, p.color_ref_a, p.color_ref_b)

  return (
    <div className="grid-sim">
      <Section title="Proses ayarları" subtitle="Kaydırıcıları değiştirin; sonuçlar anında güncellenir.">
        <SettingsBar settings={settings} setSettings={setSettings} />
        <div className="sliders">
          {meta.factors.map((f) => (
            <FactorSlider key={f.key} factor={f} value={point[f.key]}
              onChange={(v) => setPoint({ ...point, [f.key]: v })} />
          ))}
        </div>
        <button className="btn ghost" onClick={() =>
          setPoint(Object.fromEntries(meta.factors.map((f) => [f.key, (f.low + f.high) / 2])))}>
          Merkez noktaya dön
        </button>
      </Section>

      <div className="stack">
        <ErrorNote error={error} />
        <Section title="Simülasyon sonucu" subtitle={`${settings.n_applications} H₂O₂ uygulaması · hedef nem %${fmt(settings.target_moisture, 1)}`}
          actions={<button className="btn ghost" onClick={exportPdf} disabled={pdfLoading}>
            {pdfLoading ? 'PDF hazırlanıyor…' : 'PDF raporu indir'}</button>}>
          {result && (
            <>
              <div className="stats">
                <Stat label="Nihai toplam SO₂" value={fmt(result.so2_final, 0)} unit="ppm"
                  tone={result.meets_so2_limit ? 'ok' : 'bad'}
                  hint={result.meets_so2_limit ? `≤ ${goals.so2_limit} ppm limit sağlanıyor` : `${goals.so2_limit} ppm limitin üstünde`} />
                <Stat label="H₂O₂ sonrası SO₂" value={fmt(result.so2_after_dip, 0)} unit="ppm"
                  hint={`Kurutmada ${result.so2_final > result.so2_after_dip ? 'derişme' : 'kayıp'}: ${fmt(result.so2_final - result.so2_after_dip, 0)} ppm`} />
                <Stat label="H₂O₂ sonrası nem" value={fmt(result.moisture_after_dip, 1)} unit="%" />
                <Stat label="Nihai nem" value={fmt(result.moisture_final, 1)} unit="%"
                  tone={result.meets_moisture ? 'ok' : 'bad'} />
                <Stat label="Kurutma süresi" value={hoursToText(result.drying_time)} />
                <Stat label="Toplam işlem süresi" value={hoursToText(result.total_time)} />
                <Stat label="L* (parlaklık)" value={fmt(result.color_L, 1)} />
                <Stat label="a* / b*" value={`${fmt(result.color_a, 1)} / ${fmt(result.color_b, 1)}`} />
                <Stat label="ΔE (referansa göre)" value={fmt(result.color_dE, 1)}
                  tone={result.color_dE <= 3 ? 'ok' : result.color_dE > 8 ? 'bad' : ''}
                  hint="≤ 3 gözle zor ayırt edilir" />
              </div>
              <div className="swatches">
                <div><div className="swatch" style={{ background: refHex }} /><span>Referans (ticari kükürtlü)</span></div>
                <div><div className="swatch" style={{ background: labToHex(result.color_L, result.color_a, result.color_b) }} /><span>Simüle ürün</span></div>
              </div>
            </>
          )}
        </Section>

        <Section title="Tek faktör taraması"
          subtitle="Seçilen faktör aralığı boyunca değişir, diğerleri yukarıdaki değerlerde sabit kalır."
          actions={
            <div className="inline-controls">
              <select value={sweepFactor} onChange={(e) => setSweepFactor(e.target.value)}>
                {meta.factors.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
              </select>
              <select value={sweepResponse} onChange={(e) => setSweepResponse(e.target.value)}>
                {SWEEP_RESPONSES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
              </select>
            </div>
          }>
          <div className="chart">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
                <XAxis dataKey="x" type="number" domain={[factor.low, factor.high]} stroke="var(--muted)"
                  label={{ value: `${factor.label} (${factor.unit})`, position: 'insideBottom', offset: -10, fill: 'var(--muted)' }} />
                <YAxis stroke="var(--muted)" domain={['auto', 'auto']} tickFormatter={(v) => fmt(v, respMeta.digits > 1 ? 1 : 0)} />
                <Tooltip formatter={(v) => [fmt(v, respMeta.digits), respMeta.label]}
                  labelFormatter={(x) => `${factor.label}: ${fmt(x, 2)}`}
                  contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }} />
                {sweepResponse === 'so2_final' && (
                  <ReferenceLine y={goals.so2_limit} stroke="var(--bad)" strokeDasharray="6 4"
                    label={{ value: `${goals.so2_limit} ppm`, fill: 'var(--bad)', position: 'insideTopRight' }} />
                )}
                <ReferenceLine x={point[sweepFactor]} stroke="var(--accent)" strokeDasharray="2 3" />
                <Line type="monotone" dataKey="y" stroke="var(--accent)" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Section>

        <Section title="Literatür modeline göre optimum"
          subtitle="Başlangıç SO₂ hammadde özelliği olduğundan optimum her parti seviyesi için ayrı aranır (desirability, ızgara araması)."
          actions={<button className="btn" onClick={findOptimum} disabled={optLoading}>{optLoading ? 'Hesaplanıyor…' : 'Optimumu bul'}</button>}>
          {optimum ? <OptimumTable meta={meta} optimum={optimum.optimum} goals={goals} onApply={setPoint} /> :
            <p className="muted">Mevcut uygulama sayısı, hedef nem, hedefler ve model varsayımlarıyla hesaplanır.</p>}
        </Section>
      </div>
    </div>
  )
}

export function OptimumTable({ meta, optimum, goals, onApply }) {
  const controllable = meta.factors.slice(1)
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Başlangıç SO₂</th>
            {controllable.map((f) => <th key={f.key}>{f.label} <span className="muted">({f.unit})</span></th>)}
            <th>Nihai SO₂</th><th>Toplam süre</th><th>L*</th><th>ΔE</th><th>D</th>
            {onApply && <th />}
          </tr>
        </thead>
        <tbody>
          {optimum.map((o) => (
            <tr key={o.so2_initial}>
              <td><strong>{fmt(o.so2_initial, 0)}</strong></td>
              {controllable.map((f) => <td key={f.key}>{fmt(o.settings[f.key], f.step < 1 ? 2 : 0)}</td>)}
              <td className={o.responses.so2_final <= goals.so2_limit ? 'ok-text' : 'bad-text'}>{fmt(o.responses.so2_final, 0)}</td>
              <td>{hoursToText(o.responses.total_time)}</td>
              <td>{fmt(o.responses.color_L, 1)}</td>
              <td>{fmt(o.responses.color_dE, 1)}</td>
              <td>{fmt(o.desirability, 3)}</td>
              {onApply && <td><button className="btn small ghost" onClick={() => onApply(o.settings)}>Uygula</button></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
