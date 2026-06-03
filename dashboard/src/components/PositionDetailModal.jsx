import React from 'react'
import { fmt, calcTP, calcDefense } from '../utils/trading.js'

function DefenseProgress({ pos, slotSize }) {
  const def = calcDefense(pos, slotSize)
  if (!def) return <p className="modal-muted">4x dışı — defans sistemi yok</p>

  const { entryPrice, markPrice } = pos
  const { d1Price, d2Price, d3Price, isLong } = def

  const rangeTop = entryPrice
  const rangeBot = d3Price
  const span = Math.abs(rangeTop - rangeBot) || 1

  function pct(price) {
    if (isLong) {
      return Math.min(100, Math.max(0, ((rangeTop - price) / span) * 100))
    }
    return Math.min(100, Math.max(0, ((price - rangeTop) / span) * 100))
  }

  const markPct = pct(markPrice)
  const d1Pct = pct(d1Price)
  const d2Pct = pct(d2Price)

  return (
    <div className="def-progress-wrap">
      <div className="def-progress-labels">
        <span>Giriş ${fmt(entryPrice, 4)}</span>
        <span>Mark ${fmt(markPrice, 4)}</span>
        <span>Hard ${fmt(d3Price, 4)}</span>
      </div>
      <div className="def-progress-track">
        <div className="def-band band-entry" style={{ width: `${Math.min(d1Pct, 100)}%` }} />
        <div className="def-band band-d1" style={{ left: `${d1Pct}%`, width: `${Math.max(0, d2Pct - d1Pct)}%` }} />
        <div className="def-band band-d2" style={{ left: `${d2Pct}%`, width: `${Math.max(0, 100 - d2Pct)}%` }} />
        <div className="def-marker" style={{ left: `${markPct}%` }} title="Mark fiyat" />
      </div>
      <div className="def-progress-legend">
        <span><i className="dot dot-yellow" /> D1</span>
        <span><i className="dot dot-orange" /> D2</span>
        <span><i className="dot dot-red" /> D3 / Hard</span>
      </div>
    </div>
  )
}

export default function PositionDetailModal({ pos, onClose, data }) {
  if (!pos) return null

  const slotSize = (data?.balance ?? 0) / 10
  const tp = calcTP(pos)
  const def = calcDefense(pos, slotSize)
  const isFast = tp.tp_type === 'fast'

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">{pos.symbol}</h2>
            <span className={`badge ${pos.side === 'LONG' ? 'badge-long' : 'badge-short'}`}>
              {pos.side} · {pos.leverage}x
            </span>
          </div>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <section className="detail-section">
            <h3>Take Profit</h3>
            <div className="detail-grid">
              <div className="detail-card">
                <span className="detail-label">TP1 (+{tp.tp1_pct}%)</span>
                <span className="detail-price">${fmt(tp.tp1Price, 4)}</span>
                <span className="detail-usdt text-green">+{fmt(tp.tp1Usdt, 2)} USDT</span>
                <span className="detail-note">%50 kapat · qty {fmt(tp.tp1Qty, 4)}</span>
              </div>
              <div className="detail-card">
                <span className="detail-label">TP2 (+{tp.tp2_pct}%)</span>
                <span className="detail-price">${fmt(tp.tp2Price, 4)}</span>
                <span className="detail-usdt text-green">+{fmt(tp.tp2Usdt, 2)} USDT</span>
                <span className="detail-note">
                  {isFast ? '%100 kapat' : '%50 kapat'} · qty {fmt(tp.tp2Qty, 4)}
                </span>
              </div>
              <div className="detail-card">
                <span className="detail-label">Trailing</span>
                {isFast ? (
                  <span className="detail-note text-red">10x — Trailing yok</span>
                ) : (
                  <>
                    <span className="detail-price accent">callback %{tp.trailing_callback}</span>
                    <span className="detail-note">TP2 sonrası · max_prices</span>
                  </>
                )}
              </div>
            </div>
          </section>

          {def && (
            <section className="detail-section">
              <h3>Defans (4x)</h3>
              <div className="detail-grid">
                <div className="detail-card">
                  <span className="detail-label">D1 (-5%)</span>
                  <span className="detail-price accent">${fmt(def.d1Price, 4)}</span>
                  <span className="detail-usdt">+{fmt(def.d1Usdt, 2)} USDT ekle</span>
                </div>
                <div className="detail-card">
                  <span className="detail-label">D2 (-12%)</span>
                  <span className="detail-price text-red">${fmt(def.d2Price, 4)}</span>
                  <span className="detail-usdt">+{fmt(def.d2Usdt, 2)} USDT · TP dondur</span>
                </div>
                <div className="detail-card">
                  <span className="detail-label">D3 / Hard (-25%)</span>
                  <span className="detail-price text-red">${fmt(def.d3Price, 4)}</span>
                  <span className="detail-usdt">+{fmt(def.d3Usdt, 2)} USDT · Hayalet SFP</span>
                </div>
              </div>
              <DefenseProgress pos={pos} slotSize={slotSize} />
              <p className="detail-note">Mevcut aşama: D{pos.defenseLevel || 0}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
