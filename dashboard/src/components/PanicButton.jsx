import React, { useState } from 'react'

export default function PanicButton({ onPanic, disabled, compact = false }) {
  const [modalOpen, setModalOpen] = useState(false)
  const [closing, setClosing] = useState(false)

  function handleConfirm() {
    setClosing(true)
    onPanic?.()
    setTimeout(() => {
      setClosing(false)
      setModalOpen(false)
    }, 2000)
  }

  return (
    <>
      <button
        type="button"
        className={compact ? 'panic-btn-header' : 'panic-btn'}
        disabled={disabled || closing}
        onClick={() => setModalOpen(true)}
        aria-label="Panik — tüm pozisyonları kapat"
        title="Panik kapat"
      >
        {compact ? (
          <span className="panic-btn-header-text">{closing ? '…' : 'PANIK'}</span>
        ) : (
          closing ? '⏳ Kapatılıyor...' : '🚨 PANİK — TÜM POZİSYONLARI KAPAT'
        )}
      </button>

      {modalOpen && (
        <div className="modal-overlay" onClick={() => !closing && setModalOpen(false)}>
          <div className="modal panic-modal" onClick={(e) => e.stopPropagation()}>
            <div className="panic-modal-icon">⚠️</div>
            <h2 className="panic-modal-title">Panik Kapatma</h2>
            <p className="panic-modal-text">
              Tüm açık pozisyonlar MARKET emri ile anında kapatılacak. Bu işlem geri alınamaz.
            </p>
            <div className="panic-modal-actions">
              <button
                type="button"
                className="btn btn-ghost touch-target"
                disabled={closing}
                onClick={() => setModalOpen(false)}
              >
                İptal
              </button>
              <button
                type="button"
                className="btn btn-danger touch-target"
                disabled={closing || disabled}
                onClick={handleConfirm}
              >
                {closing ? 'Kapatılıyor...' : 'Evet, Hepsini Kapat'}
              </button>
            </div>
            {disabled && (
              <p className="panic-modal-hint">WebSocket bağlantısı gerekli</p>
            )}
          </div>
        </div>
      )}
    </>
  )
}
