import React from 'react'
import { fmt } from '../utils/trading.js'
import { formatPdfTimestamp, formatMacroSnippet } from '../utils/macroFormat.js'

const LEVEL_COINS = [
  { coin: 'TOTAL', label: 'TOTAL', trillion: true },
  { coin: 'OTHERS', label: 'OTHERS', billions: true },
  { coin: 'BTCUSDT', label: 'BTC' },
  { coin: 'ETHUSDT', label: 'ETH' },
  { coin: 'XAUUSDT', label: 'XAU' },
  { coin: 'XAGUSDT', label: 'XAG' },
]

function normalizeItem(raw, coin) {
  return {
    coin,
    supports: (raw?.supports || []).map(Number).filter((n) => !Number.isNaN(n)),
    resistances: (raw?.resistances || []).map(Number).filter((n) => !Number.isNaN(n)),
    snippet: formatMacroSnippet((raw?.snippet || raw?.text || '').trim()),
    markPrice: raw?.markPrice != null ? Number(raw.markPrice) : null,
    markDisplay: raw?.markDisplay ?? null,
  }
}

function formatPrice(coin, v, { trillion, billions } = {}) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (trillion) return `${fmt(n, 3)}T`
  if (billions) return `${fmt(n, 2)}B`
  if (coin.includes('BTC') || coin.includes('ETH')) {
    return n >= 1000 ? `$${fmt(n, 0)}` : `$${fmt(n, 2)}`
  }
  return fmt(n, n >= 100 ? 0 : 2)
}

function levelBarMeta(item, spec) {
  const supports = item.supports
  const resistances = item.resistances
  const price = item.markPrice
  if (!supports.length && !resistances.length) return null

  const minS = supports.length ? Math.min(...supports) : null
  const maxR = resistances.length ? Math.max(...resistances) : null
  let lo = minS ?? maxR ?? price
  let hi = maxR ?? minS ?? price
  if (price != null) {
    lo = Math.min(lo, price)
    hi = Math.max(hi, price)
  }
  if (hi <= lo) hi = lo * 1.001 || lo + 1

  let dotPct = 50
  if (price != null && hi > lo) {
    dotPct = ((price - lo) / (hi - lo)) * 100
    dotPct = Math.max(2, Math.min(98, dotPct))
  }

  let zone = 'neutral'
  if (price != null) {
    const near = (lv) => lv && Math.abs(price - lv) / lv <= 0.03
    if (resistances.some(near)) zone = 'resist'
    else if (supports.some(near)) zone = 'support'
  }

  return {
    lo,
    hi,
    minS,
    maxR,
    price,
    dotPct,
    zone,
    loLabel: minS != null ? formatPrice(item.coin, minS, spec) : '—',
    hiLabel: maxR != null ? formatPrice(item.coin, maxR, spec) : '—',
    midLabel: item.markDisplay || (price != null ? formatPrice(item.coin, price, spec) : '—'),
  }
}

function LevelBar({ item, spec }) {
  const meta = levelBarMeta(item, spec)
  if (!meta) {
    return (
      <div className="level-bar-block">
        <div className="level-bar-head">
          <span className="level-bar-coin">{spec.label}</span>
          <span className="level-bar-mid">{item.markDisplay || '—'}</span>
        </div>
        <div className="level-bar-empty">—</div>
      </div>
    )
  }

  const fillClass =
    meta.zone === 'support' ? 'level-bar-fill-support' :
    meta.zone === 'resist' ? 'level-bar-fill-resist' : 'level-bar-fill-neutral'

  return (
    <div className="level-bar-block">
      <div className="level-bar-head">
        <span className="level-bar-coin">{spec.label}</span>
        <span className="level-bar-mid">{meta.midLabel}</span>
      </div>
      <div className="level-bar-labels">
        <span>{meta.loLabel}</span>
        <span>{meta.hiLabel}</span>
      </div>
      <div className={`level-bar-container level-bar-zone-${meta.zone}`}>
        {meta.zone === 'support' && <div className="level-bar-glow level-bar-glow-left" aria-hidden />}
        {meta.zone === 'resist' && <div className="level-bar-glow level-bar-glow-right" aria-hidden />}
        <div
          className={`level-bar-fill ${fillClass}`}
          style={{ width: `${meta.dotPct}%` }}
        />
        <div className="level-bar-dot" style={{ left: `${meta.dotPct}%` }} />
      </div>
    </div>
  )
}

export default function MacroLevelsPanel({
  levels = [],
  halukPdfTimestamp = null,
}) {
  const byCoin = Object.fromEntries((levels || []).map((l) => [l.coin, l]))
  const pdfWhen = formatPdfTimestamp(halukPdfTimestamp)

  const items = LEVEL_COINS.map((spec) => ({
    spec,
    item: normalizeItem(byCoin[spec.coin], spec.coin),
  }))

  const notes = items
    .map(({ item }) => item.snippet)
    .filter(Boolean)
  const noteText = notes.length ? notes.join(' · ') : '—'

  return (
    <div className="panel macro-col-panel macro-compass">
      <div className="macro-compass-head">
        <div className="macro-compass-title">Haluk Hoca — Makro Hedefler</div>
        {pdfWhen && <div className="macro-compass-pdf">{pdfWhen}</div>}
      </div>

      <div className="macro-level-bars">
        {items.map(({ spec, item }) => (
          <LevelBar key={spec.coin} item={item} spec={spec} />
        ))}
      </div>

      <div className="hoca-note-box">
        <div className="hoca-note-title">📌 Hoca&apos;nın Notu</div>
        <div className="hoca-note-body">{noteText}</div>
      </div>
    </div>
  )
}
