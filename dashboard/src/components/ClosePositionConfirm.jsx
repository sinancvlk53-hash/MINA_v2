import React from 'react'

export default function ClosePositionConfirm({ open, pos, onConfirm, onCancel }) {
  if (!open || !pos) return null

  const sym = pos.symbol?.replace(/USDT$/, '') || pos.symbol

  return (
    <div className="manual-open-overlay" role="dialog" aria-modal="true">
      <div className="manual-open-modal close-pos-modal">
        <h2 className="manual-open-title">Pozisyon Kapat</h2>
        <p className="manual-open-sub">
          <strong>{sym}USDT {pos.side}</strong> pozisyonunu kapatmak istediğinize emin misiniz?
        </p>
        <div className="manual-open-actions">
          <button type="button" className="btn btn-ghost manual-open-btn-cancel" onClick={onCancel}>
            İptal
          </button>
          <button type="button" className="btn btn-close manual-open-btn-confirm" onClick={onConfirm}>
            Evet, Kapat
          </button>
        </div>
      </div>
    </div>
  )
}
