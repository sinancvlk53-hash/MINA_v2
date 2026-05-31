import React from 'react'

const WS_STATUS = {
  connected:    { color: '#10b981', label: 'CANLI' },
  disconnected: { color: '#ef4444', label: 'BAĞLANTI YOK' },
  error:        { color: '#ef4444', label: 'HATA' },
  connecting:   { color: '#f59e0b', label: 'BAĞLANIYOR' },
}

export default function Header({ data, status }) {
  const balance      = data?.balance != null ? data.balance.toFixed(2) : '—'
  const floatingPnl  = data?.floatingPnl
  const posCount     = data?.positionCount ?? '—'
  const engineOn     = data?.engineRunning

  const ws = WS_STATUS[status] || WS_STATUS.connecting

  const pnlColor = floatingPnl == null ? 'var(--text-dim)'
    : floatingPnl >= 0 ? 'var(--green)' : 'var(--red)'

  const pnlStr = floatingPnl != null
    ? (floatingPnl >= 0 ? '+' : '') + floatingPnl.toFixed(2) + ' USDT'
    : '—'

  return (
    <header className="header">
      {/* Logo */}
      <div className="logo">
        <div className="logo-icon">M</div>
        <div className="logo-text">
          <div className="logo-title">MINA v2</div>
          <div className="logo-sub">Algorithmic Trading</div>
        </div>
      </div>

      <div className="header-spacer" />

      {/* Bakiye */}
      <div className="stat-card">
        <div className="stat-label">Bakiye</div>
        <div className="stat-value">${balance}</div>
      </div>

      {/* Floating PnL */}
      <div className="stat-card">
        <div className="stat-label">Floating PnL</div>
        <div className="stat-value" style={{ color: pnlColor }}>{pnlStr}</div>
      </div>

      {/* Pozisyon sayısı */}
      <div className="stat-card">
        <div className="stat-label">Pozisyon</div>
        <div className="stat-value">{posCount}/10</div>
      </div>

      {/* Engine durumu */}
      <div className="stat-card">
        <div className="stat-label">Engine</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: engineOn ? 'var(--green)' : engineOn === false ? 'var(--red)' : 'var(--text-mute)',
            boxShadow: engineOn ? '0 0 7px var(--green)' : 'none',
          }} />
          <span className="stat-value" style={{
            color: engineOn ? 'var(--green)' : engineOn === false ? 'var(--red)' : 'var(--text-mute)',
            fontSize: 12
          }}>
            {engineOn ? 'AKTİF' : engineOn === false ? 'PASİF' : '—'}
          </span>
        </div>
      </div>

      {/* WS bağlantı */}
      <div className="ws-badge" style={{
        background: ws.color + '18',
        border: '1px solid ' + ws.color + '44',
        color: ws.color
      }}>
        ● {ws.label}
      </div>
    </header>
  )
}
