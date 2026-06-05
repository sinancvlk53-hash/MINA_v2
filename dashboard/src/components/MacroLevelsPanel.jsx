import React from 'react'
import { fmt } from '../utils/trading.js'

const PANEL_ORDER = [
  'TOTAL', 'OTHERS', 'BTC.D', 'USDT.D', 'ETHUSDT', 'XAUUSDT', 'XAGUSDT', 'BRENT', 'TOTAL2', 'TOTAL3',
]

const PANEL_LABELS = {
  TOTAL: 'TOTAL',
  OTHERS: 'OTHERS',
  'BTC.D': 'BTC.D',
  'USDT.D': 'USDT.D',
  ETHUSDT: 'ETH',
  XAUUSDT: 'XAU',
  XAGUSDT: 'XAG',
  BRENT: 'BRENT',
  TOTAL2: 'TOTAL2',
  TOTAL3: 'TOTAL3',
}

function normalizeItem(raw, coin) {
  return {
    coin,
    supports: raw?.supports || [],
    resistances: raw?.resistances || [],
    snippet: (raw?.snippet || raw?.text || '').trim(),
    direction: raw?.direction ?? null,
    source: raw?.source ?? null,
  }
}

function LevelList({ title, values, cls }) {
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
            {fmt(v, v >= 1000 ? 0 : 2)}
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

  return (
    <div className={`macro-card ${hasData ? 'macro-card-filled' : 'macro-card-empty'}`}>
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
      {item.snippet ? (
        <p className="macro-snippet">{item.snippet}</p>
      ) : (
        <p className="macro-snippet macro-snippet-empty">PDF veya Telegram notu bekleniyor</p>
      )}
      <LevelList title="Destek" values={item.supports} cls="macro-support" />
      <LevelList title="Direnç" values={item.resistances} cls="macro-resist" />
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
