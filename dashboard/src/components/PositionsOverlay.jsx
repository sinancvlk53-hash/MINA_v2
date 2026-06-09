import React from 'react'
import { createPortal } from 'react-dom'

export default function PositionsOverlay({ open, onClose, children }) {
  if (!open) return null

  return createPortal(
    <div className="positions-overlay" onClick={onClose} role="presentation">
      <div
        className="positions-slide-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Pozisyonlar"
      >
        <div className="positions-slide-head">
          <h2>Pozisyonlar</h2>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Kapat">
            ×
          </button>
        </div>
        <div className="positions-slide-body">
          {children}
        </div>
      </div>
    </div>,
    document.body,
  )
}
