import React from 'react'
import { fmt } from '../utils/trading.js'

const PANEL_ORDER = [
  'TOTAL', 'OTHERS', 'BTC.D', 'USDT.D', 'BTCUSDT', 'ETHUSDT', 'XAUUSDT', 'XAGUSDT', 'BRENT', 'TOTAL2', 'TOTAL3',
]

const PANEL_LABELS = {
  TOTAL: 'TOTAL',
  OTHERS: 'OTHERS',
  'BTC.D': 'BTC.D',
  'USDT.D': 'USDT.D',
  BTCUSDT: 'BTC',
  ETHUSDT: 'ETH',
  XAUUSDT: 'XAU',
  XAGUSDT: 'XAG',
  BRENT: 'BRENT',
  TOTAL2: 'TOTAL2',
  TOTAL3: 'TOTAL3',
}

const TRILLION_COINS = new Set(['TOTAL', 'TOTAL2', 'TOTAL3'])
const PCT_COINS = new Set(['BTC.D', 'USDT.D'])

function normalizeItem(raw, coin) {
  return {
    coin,
    supports: raw?.supports || [],
    resistances: raw?.resistances || [],
    snippet: (raw?.snippet || raw?.text || '').trim(),
    direction: raw?.direction ?? null,
    source: raw?.source ?? null,
    markPrice: raw?.markPrice ?? null,
    markDisplay: raw?.markDisplay ?? null,
  }
}

function formatLevel(coin, v) {
  if (TRILLION_COINS.has(coin)) return `${fmt(v, 3)}T`
  if (PCT_COINS.has(coin)) return `${fmt(v, 2)}%`
  if (coin === 'OTHERS') return `${fmt(v, 2)}B`
  if (coin === 'BTCUSDT' || coin === 'ETHUSDT') return `$${fmt(v, v >= 1000 ? 0 : 2)}`
  return fmt(v, v >= 1000 ? 0 : 2)
}

function proximityZone(price, supports, resistances) {
  if (price == null || Number.isNaN(Number(price))) {
    return { zone: 'ok', message: null }
  }
  const p = Number(price)
  const near = (level) => {
    const lv = Number(level)
    if (!lv || Number.isNaN(lv)) return false
    return Math.abs(p - lv) / lv <= 0.03
  }
  if ((resistances || []).some(near)) {
    return { zone: 'resist', message: 'Direnç bölgesinde' }
  }
  if ((supports || []).some(near)) {
    return { zone: 'support', message: 'Destek bölgesine yaklaşıyor' }
  }
  return { zone: 'ok', message: null }
}

function LevelList({ title, values, cls, coin }) {
  if (!values?.length) {
    return (
      <div className="macro-level-group">
        <span className="macro-level-title">{title}</span>
        <span className="field-hint">—</span>
      </div>
    )
  }
  return (
    <div className="macro-level-group">
      <span className="macro-level-title">{title}</span>
      <div className="macro-level-tags">
        {values.map((v) => (
          <span key={`${title}-${v}`} className={`macro-level-tag ${cls}`}>
            {formatLevel(coin, v)}
          </span>
        ))}
      </div>
    </div>
  )
}

function MacroCard({ item }) {
  const label = PANEL_LABELS[item.coin] || item.coin.replace(/USDT$/, '')
  const dir = item.direction === 'UP' ? '↑ Yukarı' : item.direction === 'DOWN' ? '↓ Aşağı' : null
  const hasData = item.snippet || item.supports?.length || item.resistances?.length
  const { zone, message } = proximityZone(item.markPrice, item.supports, item.resistances)
  const zoneClass = zone === 'resist' ? 'macro-card-zone-resist' : zone === 'support' ? 'macro-card-zone-support' : 'macro-card-zone-ok'

  return (
    <div className={`macro-card ${hasData ? 'macro-card-filled' : 'macro-card-empty'} ${zoneClass}`}>
      <div className="macro-card-head">
        <strong>{label}</strong>
        <div className="macro-card-meta">
          {dir && <span className="field-hint">{dir}</span>}
          {item.source && (
            <span className="macro-source-tag">
              {String(item.source).replace(/^HALUK_/i, '').replace(/^haluk_/i, '')}
            </span>
          )}
        </div>
      </div>
      {item.markDisplay ? (
        <div className="macro-live-price">Şu an: {item.markDisplay}</div>
      ) : item.markPrice != null ? (
        <div className="macro-live-price">Şu an: {formatLevel(item.coin, item.markPrice)}</div>
      ) : null}
      {message && <div className="macro-zone-alert">{message}</div>}
      {item.snippet ? (
        <p className="macro-snippet">{item.snippet}</p>
      ) : (
        <p className="macro-snippet macro-snippet-empty">PDF veya Telegram notu bekleniyor</p>
      )}
      <LevelList title="Destek" values={item.supports} cls="macro-support" coin={item.coin} />
      <LevelList title="Direnç" values={item.resistances} cls="macro-resist" coin={item.coin} />
    </div>
  )
}

export default function MacroLevelsPanel({ levels = [] }) {
  const byCoin = Object.fromEntries((levels || []).map((l) => [l.coin, l]))
  const items = PANEL_ORDER.map((c) => normalizeItem(byCoin[c], c))
  const filled = items.filter((i) => i.snippet || i.supports?.length || i.resistances?.length).length

  return (
    <div className="panel panel-macro">
      <div className="panel-head">
        <div>
          <span className="panel-title">Haluk Makro Panel</span>
          <span className="panel-subtitle">PDF + Telegram · işlem sinyali değil</span>
        </div>
        <span className="panel-badge">{filled}/{PANEL_ORDER.length}</span>
      </div>
      <div className="macro-grid macro-grid-wide">
        {items.map((item) => (
          <MacroCard key={item.coin} item={item} />
        ))}
      </div>
    </div>
  )
}
