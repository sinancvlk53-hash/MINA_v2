import React, { useEffect } from 'react'
import PositionChartEmbed from './PositionChartEmbed.jsx'

export default function ChartFullscreenModal({ pos, slotSize, onClose }) {
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!pos) return null

  return (
    <div className="chart-fullscreen-overlay" role="dialog" aria-modal="true" aria-label="Pozisyon grafiği">
      <header className="chart-fullscreen-head">
        <button type="button" className="chart-fullscreen-back" onClick={onClose}>
          ← Pozisyonlar
        </button>
        <div className="chart-fullscreen-meta">
          <strong>{pos.symbol?.replace(/USDT$/, '')}</strong>
          <span className={`badge ${pos.side === 'LONG' ? 'badge-long' : 'badge-short'}`}>{pos.side}</span>
        </div>
      </header>
      <div className="chart-fullscreen-body">
        <PositionChartEmbed pos={pos} slotSize={slotSize} fullscreen />
      </div>
    </div>
  )
}
