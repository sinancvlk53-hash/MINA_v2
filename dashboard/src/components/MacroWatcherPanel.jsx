import React from 'react'

function TrafficLight({ score, label }) {
  const color = score <= 3 ? 'green' : score <= 6 ? 'yellow' : 'red'
  const bg = {
    green: 'rgba(34,197,94,0.15)',
    yellow: 'rgba(234,179,8,0.15)',
    red: 'rgba(239,68,68,0.15)',
  }[color]
  const border = {
    green: '#22c55e', yellow: '#eab308', red: '#ef4444',
  }[color]

  const advice = {
    green: 'Piyasa sağlıklı — giriş uygun',
    yellow: 'Temkinli ol — seçici gir',
    red: 'Yeni giriş yapma — bekle',
  }[color]

  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: '8px',
      marginBottom: '16px',
      background: bg,
      border: `1px solid ${border}`,
    }}>
      <div style={{ fontSize: '1.1rem', fontWeight: 'bold' }}>
        Makro İklim Puanı: {score}/10 — {label}
      </div>
      <div style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '4px' }}>
        {advice}
      </div>
    </div>
  )
}

const GRID_ORDER = [
  { key: 'TOTAL', label: 'TOTAL', hint: 'Toplam kripto piyasa değeri' },
  { key: 'TOTAL2', label: 'TOTAL2', hint: 'BTC hariç toplam piyasa' },
  { key: 'TOTAL3', label: 'TOTAL3', hint: 'BTC + ETH hariç piyasa' },
  { key: 'OTHERS', label: 'OTHERS', hint: 'Altcoin piyasa payı' },
  { key: 'BTC.D', label: 'BTC.D', hint: 'Bitcoin dominansı' },
  { key: 'USDT.D', label: 'USDT.D', hint: 'Stablecoin dominansı — risk iştahı' },
  { key: 'ETH.D', label: 'ETH.D', hint: 'Ethereum dominansı' },
  { key: 'BTC', label: 'BTC', hint: 'Bitcoin fiyatı' },
  { key: 'ETH', label: 'ETH', hint: 'Ethereum fiyatı' },
  { key: 'ETH_BTC', label: 'ETH/BTC', hint: 'Altcoin sezonu göstergesi' },
  { key: 'BTC_FUNDING', label: 'BTC Fund.', hint: 'BTC perpetual funding oranı' },
  { key: 'ETH_FUNDING', label: 'ETH Fund.', hint: 'ETH perpetual funding oranı' },
  { key: 'BTC_OI', label: 'BTC OI', hint: 'Açık pozisyon hacmi' },
  { key: 'BTC_LS', label: 'BTC L/S', hint: 'Long / Short oranı' },
  { key: 'XAU', label: 'Altın', hint: 'Altın fiyatı — risk-off göstergesi' },
  { key: 'FEAR_GREED', label: 'F&G', hint: 'Korku & Açgözlülük endeksi' },
  { key: 'DXY', label: 'DXY', hint: 'Dolar endeksi' },
  { key: 'USOIL', label: 'Petrol', hint: 'Ham petrol fiyatı' },
  { key: 'SPX', label: 'S&P500', hint: 'ABD hisse endeksi' },
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

function riskScoreHint(score) {
  if (score >= 5) return 'Düşük risk — piyasa genel olarak destekleyici'
  if (score >= 3) return 'Orta risk — seçici giriş, dikkatli pozisyon'
  return 'Yüksek risk — savunma modu önerilir'
}

function macroScoreHint(score) {
  if (score >= 30) return 'Güçlü makro rüzgar — long lehine'
  if (score <= -30) return 'Zayıf makro — short / nakit lehine'
  return 'Nötr makro — yön net değil'
}

function MetricCell({ label, hint, data }) {
  if (!data) {
    return (
      <div className="makro-metric-cell makro-metric-empty">
        <span className="makro-metric-label">{label}</span>
        <span className="makro-metric-hint">{hint}</span>
        <span className="makro-metric-value">—</span>
      </div>
    )
  }
  const chg = data.change24h
  const chgText = chg != null ? `${chg >= 0 ? '+' : ''}${Number(chg).toFixed(2)}%` : null
  return (
    <div className={`makro-metric-cell ${data.stale ? 'makro-metric-stale' : ''}`}>
      <span className="makro-metric-label">{label}</span>
      <span className="makro-metric-hint">{hint}</span>
      <span className="makro-metric-value">
        {data.display ?? data.value ?? '—'}
        <span className={`makro-metric-arrow makro-dir-${data.direction || 'flat'}`}>
          {arrow(data.direction)}
        </span>
      </span>
      {chgText && <span className={`makro-metric-chg ${chg >= 0 ? 'text-green' : 'text-red'}`}>{chgText}</span>}
      {data.stale && <span className="makro-stale-tag">eski veri</span>}
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

  const srcEntries = Object.entries(sources)
  const okCount = srcEntries.filter(([, v]) => v === 'ok').length

  return (
    <div className="panel panel-makro-watcher">
      <TrafficLight
        score={w.macroWeightedScore ?? 5}
        label={w.macroWeightedLabel ?? '⚠️ DİKKATLİ'}
      />
      <div className="panel-head">
        <div>
          <span className="panel-title">Makro İzleyici</span>
          <span className="panel-subtitle">Piyasa rejimi · 15 dk güncelleme</span>
        </div>
        <div className="makro-score-badges">
          <span
            className={`makro-score-badge ${riskColor(risk)}`}
            title={`Risk skoru (0–6): ${riskScoreHint(risk)}`}
          >
            Risk {risk}/6
          </span>
          <span
            className={`makro-score-badge ${macroColor(macro)}`}
            title={`Makro skor (-100/+100): ${macroScoreHint(macro)}`}
          >
            Makro {macro >= 0 ? '+' : ''}{macro}
          </span>
        </div>
      </div>

      <div className="makro-score-explainer">
        <span>{riskScoreHint(risk)}</span>
        <span>{macroScoreHint(macro)}</span>
      </div>

      <div className={`makro-permission-banner ${permClass(permKey)}`}>
        <span className="makro-perm-label">İşlem İzni</span>
        <span className="makro-perm-value">{permLabel}</span>
      </div>

      <div className="makro-grid">
        {GRID_ORDER.map(({ key, label, hint }) => (
          <MetricCell key={key} label={label} hint={hint} data={metrics[key]} />
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
          Kaynak Sağlığı ({okCount}/{srcEntries.length} aktif)
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
