import React, { useEffect } from 'react'
import PositionChartEmbed from './PositionChartEmbed.jsx'

export default function ChartBottomSheet({ pos, slotSize, onClose }) {
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  if (!pos) return null

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="bottom-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="bottom-sheet-handle" />
        <button type="button" className="bottom-sheet-close" onClick={onClose} aria-label="Kapat">
          ✕
        </button>
        <PositionChartEmbed pos={pos} slotSize={slotSize} mobile />
      </div>
    </div>
  )
}
