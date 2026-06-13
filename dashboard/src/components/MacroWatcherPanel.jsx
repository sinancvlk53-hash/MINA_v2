import React from 'react'

const BIG5 = [
  { key: 'FEAR_GREED', label: 'F&G', kind: 'fg' },
  { key: 'BTC.D', label: 'BTC.D', kind: 'pct' },
  { key: 'TOTAL', label: 'TOTAL', kind: 'total' },
  { key: 'BTC_FUNDING', label: 'Funding', kind: 'fund' },
  { key: 'DXY', label: 'DXY', kind: 'dxy' },
]

const MUTED_KEYS = [
  { key: 'TOTAL2', label: 'TOTAL2' },
  { key: 'TOTAL3', label: 'TOTAL3' },
  { key: 'OTHERS', label: 'OTHERS' },
  { key: 'USDT.D', label: 'USDT.D' },
  { key: 'ETH.D', label: 'ETH.D' },
  { key: 'BTC', label: 'BTC' },
  { key: 'ETH', label: 'ETH' },
  { key: 'ETH_BTC', label: 'ETH/BTC' },
  { key: 'ETH_FUNDING', label: 'ETH.F' },
  { key: 'BTC_OI', label: 'OI' },
  { key: 'BTC_LS', label: 'L/S' },
  { key: 'XAU', label: 'XAU' },
  { key: 'USOIL', label: 'OIL' },
  { key: 'SPX', label: 'SPX' },
]

function trafficTone(score) {
  if (score <= 3) return 'green'
  if (score <= 6) return 'yellow'
  return 'red'
}

function permText(key) {
  if (key === 'FULL_RISK') return 'FULL_RISK'
  if (key === 'DEFENSIVE') return 'DİKKAT'
  return 'RİSKLİ'
}

function permLabelShort(label) {
  const s = String(label || '')
  if (s.includes('FULL')) return 'FULL_RISK'
  if (s.includes('DİKKAT') || s.includes('DIKKAT') || s.includes('DEFENSIVE')) return 'DİKKAT'
  return 'RİSKLİ'
}

function climateLabel(score) {
  if (score <= 3) return '✅ UYGUN'
  if (score <= 6) return '⚠️ DİKKATLİ'
  return '🚨 RİSKLİ'
}

function arrow(dir) {
  if (dir === 'up') return '↑'
  if (dir === 'down') return '↓'
  return '→'
}

function fmtChg(chg) {
  if (chg == null || Number.isNaN(Number(chg))) return '—'
  const n = Number(chg)
  const cls = n >= 0 ? 'macro-val-up' : 'macro-val-down'
  return <span className={cls}>{n >= 0 ? '+' : ''}{n.toFixed(2)}%</span>
}

function Big5Row({ spec, data }) {
  const row = data || {}
  const val = row.value
  const display = row.display ?? (val != null ? String(val) : '—')
  const chg = row.change24h
  const dir = row.direction || 'flat'

  let mid = display
  let tail = null

  if (spec.kind === 'fg') {
    const n = Number(val ?? 50)
    mid = String(Math.round(n))
    tail = (
      <div className="big5-bar-wrap">
        <div className="big5-bar" style={{ width: `${Math.max(0, Math.min(100, n))}%` }} />
      </div>
    )
  } else if (spec.kind === 'pct') {
    mid = display
    tail = <span className={`big5-dir macro-dir-${dir}`}>{arrow(dir)}</span>
  } else if (spec.kind === 'total') {
    mid = display
    tail = fmtChg(chg)
  } else if (spec.kind === 'fund') {
    const n = Number(val ?? 0)
    const cls = n > 0.03 ? 'macro-val-down' : n < -0.01 ? 'macro-val-up' : 'macro-val-neutral'
    mid = <span className={cls}>{display}</span>
    tail = null
  } else if (spec.kind === 'dxy') {
    mid = display
    tail = fmtChg(chg)
  }

  return (
    <div className="big5-row">
      <span className="big5-label">{spec.label}</span>
      <span className="big5-mid">{mid}</span>
      <span className="big5-tail">{tail}</span>
    </div>
  )
}

function mutedSnippet(key, data) {
  if (!data) return `${key} —`
  const chg = data.change24h
  const base = data.display ?? data.value ?? '—'
  if (chg != null && !Number.isNaN(Number(chg))) {
    const n = Number(chg)
    return `${key} ${base} ${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
  }
  return `${key} ${base}`
}

export default function MacroWatcherPanel({ watcher = null }) {
  const w = watcher || {}
  const metrics = w.metrics || {}
  const score = w.macroWeightedScore ?? 5
  const tone = trafficTone(score)
  const permKey = w.tradePermission || 'REDUCED_RISK'
  const perm = permText(permKey) || permLabelShort(w.tradePermissionLabel)

  const mutedParts = MUTED_KEYS.map(({ key, label }) => mutedSnippet(label, metrics[key]))

  return (
    <div className="panel macro-col-panel macro-shield">
      <div className={`macro-traffic-light-banner macro-tone-${tone}`}>
        <div className="macro-traffic-score">{score}<span className="macro-traffic-denom">/10</span></div>
        <div className="macro-traffic-label">{w.macroWeightedLabel || climateLabel(score)}</div>
        <div className="macro-traffic-perm">{perm}</div>
      </div>

      <div className="macro-big5">
        {BIG5.map((spec) => (
          <Big5Row key={spec.key} spec={spec} data={metrics[spec.key]} />
        ))}
      </div>

      <div className="muted-metrics">{mutedParts.join(' · ')}</div>
    </div>
  )
}
