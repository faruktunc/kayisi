export function Section({ title, subtitle, actions, children }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, unit, tone, hint }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit"> {unit}</span>}
      </div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function FactorSlider({ factor, value, onChange }) {
  const digits = factor.step < 1 ? (factor.step < 0.1 ? 2 : 1) : 0
  return (
    <label className="slider">
      <div className="slider-head">
        <span>{factor.label}</span>
        <span className="slider-value">
          {Number(value).toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}{' '}
          <span className="muted">{factor.unit}</span>
        </span>
      </div>
      <input type="range" min={factor.low} max={factor.high} step={factor.step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} />
      <div className="slider-range muted">
        <span>{factor.low}</span>
        <span>{factor.high}</span>
      </div>
    </label>
  )
}

export function SettingsBar({ settings, setSettings }) {
  return (
    <div className="settings-bar">
      <label>
        H₂O₂ uygulama sayısı
        <select value={settings.n_applications}
          onChange={(e) => setSettings({ ...settings, n_applications: Number(e.target.value) })}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <label>
        Hedef nem (% yaş baz)
        <input type="number" min={18} max={28} step={0.5} value={settings.target_moisture}
          onChange={(e) => setSettings({ ...settings, target_moisture: Number(e.target.value) })} />
      </label>
      <span className="muted small">Kurutma bu neme inince biter; kurutma süresi yanıttır.</span>
    </div>
  )
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <div className="error">{error}</div>
}
