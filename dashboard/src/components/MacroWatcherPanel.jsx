import React from 'react'

const GRID_ORDER = [
  { key: 'TOTAL', label: 'TOTAL' },
  { key: 'TOTAL2', label: 'TOTAL2' },
  { key: 'TOTAL3', label: 'TOTAL3' },
  { key: 'OTHERS', label: 'OTHERS' },
  { key: 'BTC.D', label: 'BTC.D' },
  { key: 'USDT.D', label: 'USDT.D' },
  { key: 'ETH.D', label: 'ETH.D' },
  { key: 'BTC', label: 'BTC' },
  { key: 'ETH', label: 'ETH' },
  { key: 'ETH_BTC', label: 'ETH/BTC' },
  { key: 'BTC_FUNDING', label: 'BTC Fund.' },
  { key: 'ETH_FUNDING', label: 'ETH Fund.' },
  { key: 'BTC_OI', label: 'BTC OI' },
  { key: 'BTC_LS', label: 'BTC L/S' },
  { key: 'XAU', label: 'Altın' },
  { key: 'FEAR_GREED', label: 'F&G' },
  { key: 'DXY', label: 'DXY' },
  { key: 'USOIL', label: 'Petrol' },
  { key: 'SPX', label: 'S&P500' },
]

const SOURCE_LABELS = {
  coingecko: 'CoinGecko',
  binance_ticker: 'Binance',
  binance_funding: 'Funding',
  binance_oi: 'OI',
  binance_ls: 'L/S',
  fear_greed: 'F&G API',
  dxy: 'DXY',
  usoil: 'Petrol',
  spx: 'S&P500',
  xau: 'Altın',
}

function arrow(dir) {
  if (dir === 'up') return '↑'
  if (dir === 'down') return '↓'
  return '→'
}

function riskColor(score) {
  if (score >= 5) return 'macro-score-green'
  if (score >= 3) return 'macro-score-yellow'
  return 'macro-score-red'
}

function macroColor(score) {
  if (score >= 30) return 'macro-score-green'
  if (score <= -30) return 'macro-score-red'
  return 'macro-score-yellow'
}

function permClass(key) {
  if (key === 'FULL_RISK') return 'macro-perm-full'
  if (key === 'DEFENSIVE') return 'macro-perm-defensive'
  return 'macro-perm-reduced'
}

function MetricCell({ label, data }) {
  if (!data) {
    return (
      <div className="makro-metric-cell makro-metric-empty">
        <span className="makro-metric-label">{label}</span>
        <span className="makro-metric-value">—</span>
      </div>
    )
  }
  const chg = data.change24h
  const chgText = chg != null ? `${chg >= 0 ? '+' : ''}${Number(chg).toFixed(2)}%` : null
  return (
    <div className={`makro-metric-cell ${data.stale ? 'makro-metric-stale' : ''}`}>
      <span className="makro-metric-label">{label}</span>
      <span className="makro-metric-value">
        {data.display ?? data.value ?? '—'}
        <span className={`makro-metric-arrow makro-dir-${data.direction || 'flat'}`}>
          {arrow(data.direction)}
        </span>
      </span>
      {chgText && <span className={`makro-metric-chg ${chg >= 0 ? 'text-green' : 'text-red'}`}>{chgText}</span>}
      {data.stale && <span className="makro-stale-tag">eski</span>}
    </div>
  )
}

export default function MacroWatcherPanel({ watcher = null }) {
  const w = watcher || {}
  const metrics = w.metrics || {}
  const risk = w.riskScore ?? 0
  const macro = w.macroScore ?? 0
  const permKey = w.tradePermission || 'REDUCED_RISK'
  const permLabel = w.tradePermissionLabel || '🟡 RİSKLİ'
  const combos = w.combinations || []
  const sources = w.sources || {}
  const updatedAt = w.updatedAt

  const srcEntries = Object.entries(sources)
  const okCount = srcEntries.filter(([, v]) => v === 'ok').length

  return (
    <div className="panel panel-makro-watcher">
      <div className="panel-head">
        <div>
          <span className="panel-title">Makro İzleyici</span>
          <span className="panel-subtitle">Piyasa rejimi · 15 dk güncelleme</span>
          {updatedAt && (
            <span className="panel-subtitle makro-updated">
              Son: {String(updatedAt).replace('T', ' ').slice(0, 16)}
            </span>
          )}
        </div>
        <div className="makro-score-badges">
          <span className={`makro-score-badge ${riskColor(risk)}`} title="Risk Skoru (0-6)">
            Risk {risk}/6
          </span>
          <span className={`makro-score-badge ${macroColor(macro)}`} title="Macro Skor (-100/+100)">
            Macro {macro >= 0 ? '+' : ''}{macro}
          </span>
        </div>
      </div>

      <div className={`makro-permission-banner ${permClass(permKey)}`}>
        <span className="makro-perm-label">İşlem İzni</span>
        <span className="makro-perm-value">{permLabel}</span>
      </div>

      <div className="makro-grid">
        {GRID_ORDER.map(({ key, label }) => (
          <MetricCell key={key} label={label} data={metrics[key]} />
        ))}
      </div>

      {combos.length > 0 && (
        <div className="makro-combos">
          <div className="makro-section-title">Kombinasyon Analizi</div>
          <ul>
            {combos.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="makro-sources">
        <div className="makro-section-title">
          Kaynak Sağlığı ({okCount}/{srcEntries.length} ok)
        </div>
        <div className="makro-source-tags">
          {srcEntries.map(([k, v]) => (
            <span key={k} className={`makro-source-tag ${v === 'ok' ? 'ok' : v === 'skip' ? 'skip' : 'err'}`}>
              {SOURCE_LABELS[k] || k}: {v === 'ok' ? '✓' : v === 'skip' ? '—' : '✗'}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
