import React from 'react'
import PanicButton from './PanicButton.jsx'

const WS_STATUS = {
  connected:    { color: '#0ecb81', label: 'CANLI' },
  disconnected: { color: '#f6465d', label: 'KESİK' },
  error:        { color: '#f6465d', label: 'HATA' },
  connecting:   { color: '#f0b90b', label: 'BAĞLANIYOR' },
}

export default function Header({ data, status, onPanic }) {
  const balance     = data?.balance
  const dailyPnl    = data?.dailyPnl ?? data?.floatingPnl
  const posCount    = data?.positionCount ?? 0
  const winRate     = data?.derr?.winRate ?? data?.winRate
  const ws          = WS_STATUS[status] || WS_STATUS.connecting
  const wsConnected = status === 'connected'

  const pnlPositive = dailyPnl != null && dailyPnl >= 0
  const pnlStr = dailyPnl != null
    ? `${dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)}`
    : '—'

  const winStr = winRate != null ? `${Number(winRate).toFixed(1)}%` : '—'
  const riskKill = data?.riskStatus?.level === 'kill' || data?.riskStatus?.newEntriesBlocked

  return (
    <>
      {riskKill && (
        <div className="risk-alarm-banner" role="alert">
          KRİTİK: Günlük zarar limiti aşıldı — yeni pozisyon açılmıyor. Mevcut pozisyonlar yönetiliyor.
        </div>
      )}
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          <span className="header-logo-mark">◆</span>
          <div className="header-logo-text">
            <div className="header-logo-title">MINA v2</div>
          </div>
        </div>
      </div>

      <div className="header-center">
        <div className="header-stats">
          <div className="header-stat">
            <span className="header-stat-label">Bakiye</span>
            <span className="header-stat-value">
              {balance != null ? balance.toFixed(2) : '—'}
            </span>
          </div>
          <div className="header-stat">
            <span className="header-stat-label">PnL</span>
            <span className={`header-stat-value ${pnlPositive ? 'text-green' : 'text-red'}`}>
              {pnlStr}
            </span>
          </div>
          <div className="header-stat">
            <span className="header-stat-label">Pozisyon</span>
            <span className="header-stat-value">{posCount}/10</span>
          </div>
          <div className="header-stat">
            <span className="header-stat-label">Win Rate</span>
            <span className="header-stat-value accent">{winStr}</span>
          </div>
        </div>
      </div>

      <div className="header-right">
        <div className="header-ws" style={{ '--ws-color': ws.color }}>
          <span className="header-ws-dot" />
          <span className="header-ws-label">{ws.label}</span>
        </div>
        <PanicButton onPanic={onPanic} disabled={!wsConnected} compact />
      </div>
    </header>
    </>
  )
}
