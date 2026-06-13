import React, { useMemo, useState } from 'react'
import { fmt } from '../utils/trading.js'
import {
  formatMacroSnippet,
  formatMacroDirection,
  formatMacroSource,
  formatPdfTimestamp,
} from '../utils/macroFormat.js'

const COINS = [
  { coin: 'TOTAL', label: 'TOTAL', trillion: true },
  { coin: 'OTHERS', label: 'OTHERS', billions: true },
  { coin: 'BTCUSDT', label: 'BTC' },
  { coin: 'ETHUSDT', label: 'ETH' },
  { coin: 'XAUUSDT', label: 'XAU' },
  { coin: 'XAGUSDT', label: 'XAG' },
  { coin: 'BRENT', label: 'BRENT' },
]

function formatPrice(coin, v, spec = {}) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (spec.trillion) return `${fmt(n, 3)}T`
  if (spec.billions) return `${fmt(n, 2)}B`
  if (coin.includes('BTC') || coin.includes('ETH')) {
    return n >= 1000 ? `$${fmt(n, 0)}` : `$${fmt(n, 2)}`
  }
  return fmt(n, n >= 100 ? 0 : 2)
}

function normalizeLevel(raw, spec) {
  const supports = (raw?.supports || []).map(Number).filter((n) => !Number.isNaN(n))
  const resistances = (raw?.resistances || []).map(Number).filter((n) => !Number.isNaN(n))
  const markPrice = raw?.markPrice != null ? Number(raw.markPrice) : null
  const snippet = formatMacroSnippet((raw?.snippet || raw?.text || '').trim())
  const direction = raw?.direction || null

  let zone = 'neutral'
  if (markPrice != null) {
    const near = (lv) => lv && Math.abs(markPrice - lv) / lv <= 0.03
    if (resistances.some(near)) zone = 'resist'
    else if (supports.some(near)) zone = 'support'
  }

  const updatedAt =
    formatPdfTimestamp(raw?.updated_at) ||
    formatMacroSource(raw?.source) ||
    null

  return {
    coin: spec.coin,
    label: spec.label,
    spec,
    supports,
    resistances,
    snippet,
    direction,
    markPrice,
    markDisplay: raw?.markDisplay || (markPrice != null ? formatPrice(spec.coin, markPrice, spec) : '—'),
    zone,
    updatedAt,
    hasLevels: supports.length > 0 || resistances.length > 0,
  }
}

function MacroChip({ item, onClick }) {
  const dir = formatMacroDirection(item.direction)
  const zoneClass =
    item.zone === 'support' ? 'macro-analysis-chip-support' :
    item.zone === 'resist' ? 'macro-analysis-chip-resist' : ''

  const sTxt = item.supports.length
    ? item.supports.slice(0, 2).map((v) => formatPrice(item.coin, v, item.spec)).join(' · ')
    : '—'
  const rTxt = item.resistances.length
    ? item.resistances.slice(0, 2).map((v) => formatPrice(item.coin, v, item.spec)).join(' · ')
    : '—'

  return (
    <button
      type="button"
      className={`macro-analysis-chip ${zoneClass}`}
      onClick={() => onClick(item)}
    >
      <div className="macro-analysis-chip-head">
        <span className="macro-analysis-chip-coin">{item.label}</span>
        {dir && <span className={`macro-analysis-chip-dir ${dir.cls}`}>{dir.text}</span>}
      </div>
      <div className="macro-analysis-chip-row">
        <span className="macro-analysis-chip-label macro-support">S</span>
        <span className="macro-analysis-chip-val">{sTxt}</span>
      </div>
      <div className="macro-analysis-chip-row">
        <span className="macro-analysis-chip-label macro-resist">R</span>
        <span className="macro-analysis-chip-val">{rTxt}</span>
      </div>
      <div className="macro-analysis-chip-price">{item.markDisplay}</div>
    </button>
  )
}

function MacroModal({ item, onClose }) {
  if (!item) return null
  const dir = formatMacroDirection(item.direction)

  return (
    <div className="macro-analysis-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="macro-analysis-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="macro-modal-title"
      >
        <div className="macro-analysis-modal-head">
          <h3 id="macro-modal-title" className="macro-analysis-modal-title">
            {item.label}
            {dir && <span className={`macro-analysis-modal-dir ${dir.cls}`}>{dir.text}</span>}
          </h3>
          <button type="button" className="macro-analysis-modal-close" onClick={onClose} aria-label="Kapat">
            ×
          </button>
        </div>

        <div className="macro-analysis-modal-price">
          Güncel fiyat: <strong>{item.markDisplay}</strong>
        </div>

        <div className="macro-analysis-modal-levels">
          <div className={`macro-analysis-level-col ${item.zone === 'support' ? 'macro-analysis-level-hot' : ''}`}>
            <div className="macro-analysis-level-title macro-support">Destek</div>
            {item.supports.length
              ? item.supports.map((v) => (
                <div key={`s-${v}`} className="macro-analysis-level-val">{formatPrice(item.coin, v, item.spec)}</div>
              ))
              : <div className="macro-analysis-level-val">—</div>}
          </div>
          <div className={`macro-analysis-level-col ${item.zone === 'resist' ? 'macro-analysis-level-hot' : ''}`}>
            <div className="macro-analysis-level-title macro-resist">Direnç</div>
            {item.resistances.length
              ? item.resistances.map((v) => (
                <div key={`r-${v}`} className="macro-analysis-level-val">{formatPrice(item.coin, v, item.spec)}</div>
              ))
              : <div className="macro-analysis-level-val">—</div>}
          </div>
        </div>

        <div className="macro-analysis-modal-snippet">
          <div className="macro-analysis-snippet-label">Hoca&apos;nın Notu</div>
          <div className="macro-analysis-snippet-body">
            {item.snippet || '—'}
          </div>
        </div>

        {item.updatedAt && (
          <div className="macro-analysis-modal-footer">
            Son güncelleme: {item.updatedAt}
          </div>
        )}
      </div>
    </div>
  )
}

export default function MacroAnalysisPanel({ levels = [] }) {
  const [selected, setSelected] = useState(null)

  const items = useMemo(() => {
    const byCoin = Object.fromEntries((levels || []).map((l) => [l.coin, l]))
    return COINS.map((spec) => normalizeLevel(byCoin[spec.coin], spec))
  }, [levels])

  return (
    <div className="macro-analysis-panel">
      <div className="macro-analysis-head">Makro Analiz</div>
      <div className="macro-analysis-scroll">
        {items.map((item) => (
          <MacroChip key={item.coin} item={item} onClick={setSelected} />
        ))}
      </div>
      {selected && (
        <MacroModal item={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
