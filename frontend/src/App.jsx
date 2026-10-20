import { useEffect, useMemo, useState } from 'react'
import { api } from './api/client.js'
import SimulatorPage from './pages/SimulatorPage.jsx'
import LiteraturePage from './pages/LiteraturePage.jsx'
import DesignComparisonPage from './pages/DesignComparisonPage.jsx'
import RunTablePage from './pages/RunTablePage.jsx'
import AssumptionsPage from './pages/AssumptionsPage.jsx'

const TABS = [
  { key: 'simulator', label: 'Simülatör' },
  { key: 'comparison', label: 'Desen karşılaştırma' },
  { key: 'table', label: 'Deney tablosu' },
  { key: 'literature', label: 'Literatür kalibrasyonu' },
  { key: 'assumptions', label: 'Model varsayımları' },
]

export default function App() {
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('simulator')
  const [settings, setSettings] = useState({ n_applications: 1, target_moisture: 22 })
  const [goals, setGoals] = useState(null)
  const [overrides, setOverrides] = useState({})
  const [point, setPoint] = useState(null)

  useEffect(() => {
    api.meta()
      .then((m) => {
        setMeta(m)
        setSettings(m.default_settings)
        setGoals(m.default_goals)
        setPoint(Object.fromEntries(m.factors.map((f) => [f.key, (f.low + f.high) / 2])))
      })
      .catch((e) => setError(e.message))
  }, [])

  const nOverrides = Object.keys(overrides).length
  const shared = useMemo(
    () => ({ meta, settings, setSettings, goals, setGoals, overrides, setOverrides, point, setPoint }),
    [meta, settings, goals, overrides, point],
  )

  if (error) {
    return (
      <div className="boot">
        <h1>Sunucuya bağlanılamadı</h1>
        <p>{error}</p>
        <p className="muted">Backend çalışıyor mu? <code>cd backend && .venv/bin/python run.py</code></p>
      </div>
    )
  }
  if (!meta || !goals || !point) return <div className="boot">Yükleniyor…</div>

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden>◐</span>
          <div>
            <h1>Kuru kayısı desülfitleme — proses simülatörü</h1>
            <p>Ardışık H₂O₂ uygulaması + vakumlu kurutma · literatür tabanlı sanal model ve deney deseni seçimi</p>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key}
              className={tab === t.key ? 'tab active' : 'tab'} onClick={() => setTab(t.key)}>
              {t.label}
              {t.key === 'assumptions' && nOverrides > 0 && <span className="pill">{nOverrides}</span>}
            </button>
          ))}
        </nav>
      </header>

      <div className="banner">
        <strong>Varsayım uyarısı:</strong> SO₂ kinetiği iki literatür çalışmasından kalibre edilmiştir; kurutma ve renk
        modelleri bu ürüne ait veri olmadığından varsayımdır. Sonuçlar gerçek ölçüm yerine geçmez; desen seçimi ve
        aralıkların sınanması içindir.
      </div>

      <main className="content">
        {tab === 'simulator' && <SimulatorPage {...shared} />}
        {tab === 'comparison' && <DesignComparisonPage {...shared} />}
        {tab === 'table' && <RunTablePage {...shared} />}
        {tab === 'literature' && <LiteraturePage {...shared} />}
        {tab === 'assumptions' && <AssumptionsPage {...shared} />}
      </main>
    </div>
  )
}
