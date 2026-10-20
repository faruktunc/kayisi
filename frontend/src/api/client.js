const BASE = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `İstek başarısız (${res.status})`)
  return data
}

// POST ile üretilen dosyayı (PDF) indirir
async function download(path, body, filename) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.error || `PDF oluşturulamadı (${res.status})`)
  }
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  meta: () => request('/meta'),
  literature: () => request('/literature'),
  simulate: (body) => post('/simulate', body),
  sweep: (body) => post('/simulate/sweep', body),
  optimum: (body) => post('/simulate/optimum', body),
  designs: () => request('/designs'),
  design: (key, seed) => request(`/designs/${key}?seed=${seed}`),
  designCsvUrl: (key, seed) => `${BASE}/designs/${key}/csv?seed=${seed}`,
  designPdfUrl: (key, seed, conditions = {}) => {
    const q = new URLSearchParams({ seed })
    Object.entries(conditions).forEach(([k, v]) => { if (v !== '' && v != null) q.set(k, v) })
    return `${BASE}/designs/${key}/pdf?${q}`
  },
  evaluate: (body) => post('/evaluate', body),
  comparisonPdf: (result) => download('/reports/comparison', { result }, 'desen_karsilastirma_raporu.pdf'),
  simulationPdf: (body) => download('/reports/simulation', body, 'simulasyon_raporu.pdf'),
}
