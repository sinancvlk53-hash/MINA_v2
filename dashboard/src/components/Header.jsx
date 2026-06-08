import React, { useState } from 'react'
import PanicButton from './PanicButton.jsx'

const WS_STATUS = {
  connected:    { color: '#0ecb81', label: 'CANLI' },
  disconnected: { color: '#f6465d', label: 'KESİK' },
  error:        { color: '#f6465d', label: 'HATA' },
  connecting:   { color: '#f0b90b', label: 'BAĞLANIYOR' },
}

function formatWinRate(data) {
  const derr = data?.derr ?? {}
  const total = derr.totalTrades ?? data?.totalTrades
  const winRate = derr.winRate ?? data?.winRate
  if (total == null || total === 0) {
    return winRate != null ? `${total ?? 0} işlem %${Number(winRate).toFixed(1)}` : '—'
  }
  const pct = winRate != null ? Number(winRate).toFixed(1) : '0.0'
  return `${total} işlem %${pct}`
}

function fmtPnl(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)} USDT`
}

function fmtTrade(trade) {
  if (!trade?.symbol) return '—'
  const pnl = trade.pnl != null ? fmtPnl(trade.pnl) : '—'
  return `${trade.symbol} (${pnl})`
}

function fmtUsdt(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return `${Math.round(Number(v)).toLocaleString('en-US')} USDT`
}

function fmtBtc(price) {
  if (price == null || Number.isNaN(Number(price))) return '—'
  const n = Number(price)
  return n >= 1000 ? n.toLocaleString('en-US', { maximumFractionDigits: 0 }) : n.toFixed(2)
}

function WinRateModal({ open, derr, onClose }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className="win-rate-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Win rate detayları"
      >
        <div className="win-rate-modal-head">
          <h2>Win Rate — DERR</h2>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Kapat">×</button>
        </div>
        <div className="win-rate-detail-grid win-rate-modal-grid">
          <div className="win-rate-detail-item">
            <span>Toplam işlem</span>
            <strong>{derr.totalTrades ?? '—'}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>Kazanan</span>
            <strong className="text-green">{derr.winningTrades ?? '—'}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>Kaybeden</span>
            <strong className="text-red">{derr.losingTrades ?? '—'}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>En iyi işlem</span>
            <strong>{fmtTrade(derr.bestTrade)}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>En kötü işlem</span>
            <strong>{fmtTrade(derr.worstTrade)}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>Ortalama kâr</span>
            <strong className="text-green">{fmtPnl(derr.avgProfit)}</strong>
          </div>
          <div className="win-rate-detail-item">
            <span>Ortalama zarar</span>
            <strong className="text-red">{fmtPnl(derr.avgLoss)}</strong>
          </div>
          <div className="win-rate-detail-item win-rate-detail-wide">
            <span>Toplam realize PnL</span>
            <strong className={derr.netPnl >= 0 ? 'text-green' : 'text-red'}>
              {fmtPnl(derr.netPnl)}
            </strong>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Header({ data, status, onPanic, onLogout, onPositionsClick }) {
  const [winDetailOpen, setWinDetailOpen] = useState(false)
  const bd = data?.balanceBreakdown ?? {}
  const totalBal = bd.total ?? data?.balance
  const inUse = bd.inUse
  const available = bd.available
  const totalPnl = data?.totalPnl ?? (
    data?.dailyPnl != null && data?.floatingPnl != null
      ? data.dailyPnl + data.floatingPnl
      : (data?.dailyPnl ?? data?.floatingPnl)
  )
  const posCount = data?.positionCount ?? 0
  const ws = WS_STATUS[status] || WS_STATUS.connecting
  const wsConnected = status === 'connected'
  const derr = data?.derr ?? {}
  const btcPrice = data?.btcMarkPrice

  const pnlPositive = totalPnl != null && totalPnl >= 0
  const pnlStr = totalPnl != null
    ? `${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}`
    : '—'

  const winStr = formatWinRate(data)
  const riskKill = data?.riskStatus?.newEntriesBlocked === true

  return (
    <>
      {riskKill && (
        <div className="risk-alarm-banner" role="alert">
          KRİTİK: Günlük zarar limiti (%20) aşıldı — tüm pozisyonlar kapatıldı, motor durduruldu.
        </div>
      )}
      <header className="header header-v2">
        <div className="header-v2-main">
          <div className="header-v2-top">
            <div className="header-brand-block">
              <div className="header-logo-title">MINA v2</div>
              <div className="header-btc-hero">
                <span className="header-btc-label">BTC</span>
                <span className="header-btc-value">${fmtBtc(btcPrice)}</span>
              </div>
            </div>
            <div className="header-v2-actions">
              <div className="header-ws" style={{ '--ws-color': ws.color }}>
                <span className="header-ws-dot" />
                <span className="header-ws-label">{ws.label}</span>
              </div>
              {onLogout && (
                <button type="button" className="header-logout-btn" onClick={onLogout} title="Çıkış">
                  Çıkış
                </button>
              )}
              <PanicButton onPanic={onPanic} disabled={!wsConnected} compact />
            </div>
          </div>

          <div className="header-balance-stack">
            <div className="header-bal-line">
              <span className="header-bal-label">Bakiye</span>
              <span className="header-bal-value">{fmtUsdt(totalBal)}</span>
            </div>
            <div className="header-bal-line">
              <span className="header-bal-label">İşlemde</span>
              <span className="header-bal-value">{fmtUsdt(inUse)}</span>
            </div>
            <div className="header-bal-line">
              <span className="header-bal-label">Boşta</span>
              <span className="header-bal-value">{fmtUsdt(available)}</span>
            </div>
          </div>

          <div className="header-stats">
            <button
              type="button"
              className="header-stat header-stat-btn header-stat-pnl"
              onClick={() => onPositionsClick?.()}
              aria-label="Pozisyonları göster"
            >
              <span className="header-stat-label">PnL</span>
              <span className={`header-stat-value ${pnlPositive ? 'text-green' : 'text-red'}`}>
                {pnlStr}
              </span>
            </button>
            <div className="header-stat">
              <span className="header-stat-label">Pozisyon</span>
              <span className="header-stat-value">{posCount}/10</span>
            </div>
            <button
              type="button"
              className={`header-stat header-stat-winrate header-stat-btn ${winDetailOpen ? 'open' : ''}`}
              onClick={() => setWinDetailOpen(true)}
              aria-label="Win rate detayları"
            >
              <span className="header-stat-label">Win Rate</span>
              <span className="header-stat-value accent">{winStr}</span>
            </button>
          </div>
        </div>
      </header>

      <WinRateModal
        open={winDetailOpen}
        derr={derr}
        onClose={() => setWinDetailOpen(false)}
      />
    </>
  )
}
