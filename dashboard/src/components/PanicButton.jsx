import React, { useState, useEffect } from 'react'

export default function PanicButton({ onPanic, disabled }) {
  const [phase, setPhase] = useState('idle') // idle | confirm | closing | done

  useEffect(() => {
    if (phase === 'confirm') {
      const t = setTimeout(() => setPhase('idle'), 4000)
      return () => clearTimeout(t)
    }
    if (phase === 'done') {
      const t = setTimeout(() => setPhase('idle'), 3000)
      return () => clearTimeout(t)
    }
  }, [phase])

  function handleClick() {
    if (disabled || phase === 'closing') return
    if (phase === 'idle') {
      setPhase('confirm')
    } else if (phase === 'confirm') {
      setPhase('closing')
      onPanic?.()
      setTimeout(() => setPhase('done'), 2500)
    }
  }

  const cfg = {
    idle:    { bg: 'linear-gradient(135deg,#ef4444,#b91c1c)', border: '#ef4444', shadow: '0 4px 18px #ef444430', label: '🚨 PANİK — TÜM POZİSYONLARI KAPAT' },
    confirm: { bg: 'linear-gradient(135deg,#dc2626,#7f1d1d)', border: '#fca5a5', shadow: '0 0 28px #ef444460', label: '⚠️  EMİN MİSİN? — TEKRAR TIKLA' },
    closing: { bg: '#0f1824',                                  border: '#1c2a3a', shadow: 'none',               label: '⏳ Kapatılıyor...' },
    done:    { bg: 'linear-gradient(135deg,#065f46,#047857)', border: '#10b981', shadow: '0 4px 18px #10b98130', label: '✅ Tüm pozisyonlar kapatıldı' },
  }
  const s = cfg[phase] || cfg.idle

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <button
        className="panic-btn"
        onClick={handleClick}
        disabled={disabled || phase === 'closing'}
        style={{ background: s.bg, borderColor: s.border, color: '#fff', boxShadow: s.shadow }}
      >
        {s.label}
      </button>

      {phase === 'confirm' && (
        <div style={{ textAlign: 'center', color: '#fca5a5', fontSize: 10, fontWeight: 600 }}>
          4 saniye içinde otomatik iptal
        </div>
      )}
      {disabled && phase === 'idle' && (
        <div style={{ textAlign: 'center', color: 'var(--text-mute)', fontSize: 10 }}>
          WebSocket bağlantısı gerekli
        </div>
      )}
    </div>
  )
}
