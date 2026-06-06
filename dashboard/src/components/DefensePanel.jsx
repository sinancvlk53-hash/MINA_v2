import React from 'react'
import { fmt, calcDefense, calcBreakevenPrice, defenseStageLabel } from '../utils/trading.js'

function DefenseMiniCard({ pos, slotSize, breakevenMult }) {
  const def = calcDefense(pos, slotSize)
  const stage = defenseStageLabel(pos.defenseLevel || 0)
  const isLong = pos.side === 'LONG'
  const bePrice = calcBreakevenPrice(pos, breakevenMult)
  const liq = pos.liqPrice

  return (
    <div className="def-mini-card">
      <div className="def-mini-head">
        <div>
          <span className="def-mini-symbol">{pos.symbol.replace(/USDT$/, '')}</span>
          <span className={`badge sm ${isLong ? 'badge-long' : 'badge-short'}`}>{pos.side}</span>
          <span className="badge sm dim">{pos.leverage}x</span>
        </div>
        <span className={`def-stage ${stage.cls}`}>{stage.text}</span>
      </div>

      <div className="def-mini-mark">
        Giriş <strong className="mono">${fmt(pos.entryPrice, 4)}</strong>
        {' · '}
        Mark <strong className="mono">${fmt(pos.markPrice, 4)}</strong>
      </div>

      <div className="def-mini-levels def-mini-levels-full">
        <div className="def-mini-level def-mini-level-liq">
          <span className="lvl-liq">Likidasyon</span>
          <span className="mono">${fmt(liq, 4)}</span>
        </div>
        <div className="def-mini-level def-mini-level-be">
          <span className="lvl-be">Breakeven</span>
          <span className="mono">${fmt(bePrice, 4)}</span>
        </div>
        {def ? (
          <>
            <div className="def-mini-level">
              <span className="lvl-d1">D1</span>
              <span className="mono">${fmt(def.d1Price, 4)}</span>
            </div>
            <div className="def-mini-level">
              <span className="lvl-d2">D2</span>
              <span className="mono">${fmt(def.d2Price, 4)}</span>
            </div>
            <div className="def-mini-level">
              <span className="lvl-d3">D3 / Hard</span>
              <span className="mono">${fmt(def.hardStop, 4)}</span>
            </div>
          </>
        ) : (
          <p className="def-mini-muted">{pos.leverage}x — D1/D2/D3 yok</p>
        )}
      </div>

      <div className={`def-mini-pnl ${pos.pnlUSDT >= 0 ? 'text-green' : 'text-red'}`}>
        {pos.pnlUSDT >= 0 ? '+' : ''}{fmt(pos.pnlUSDT, 2)} USDT
        {' · '}
        ROE {fmt(pos.roe, 2)}%
      </div>
    </div>
  )
}

function DerrSummary({ data }) {
  const derr = data?.derr ?? {}
  const positions = data?.positions ?? []
  const totalPnl = derr.netPnl ?? data?.floatingPnl
  const totalTrades = derr.totalTrades ?? 0
  const winRate = derr.winRate ?? data?.winRate
  const winDetail = totalTrades > 0
    ? `${totalTrades} işlem %${Number(winRate ?? 0).toFixed(1)}`
    : (winRate != null ? `0 işlem %${Number(winRate).toFixed(1)}` : '—')
  const best = derr.bestCoin ?? (positions.length
    ? positions.reduce((a, b) => (a.pnlUSDT > b.pnlUSDT ? a : b)).symbol.replace(/USDT$/, '')
    : '—')
  const worst = derr.worstCoin ?? (positions.length
    ? positions.reduce((a, b) => (a.pnlUSDT < b.pnlUSDT ? a : b)).symbol.replace(/USDT$/, '')
    : '—')

  return (
    <div className="derr-box">
      <div className="derr-title">DERR Özeti</div>
      <div className="derr-grid">
        <div className="derr-item full">
          <span className="derr-label">Kazanma Oranı (DERR)</span>
          <span className="derr-value accent">{winDetail}</span>
        </div>
        <div className="derr-item">
          <span className="derr-label">En İyi Coin</span>
          <span className="derr-value text-green">{best}</span>
        </div>
        <div className="derr-item">
          <span className="derr-label">En Kötü Coin</span>
          <span className="derr-value text-red">{worst}</span>
        </div>
        <div className="derr-item full">
          <span className="derr-label">Toplam Net PnL</span>
          <span className={`derr-value ${totalPnl >= 0 ? 'text-green' : 'text-red'}`}>
            {totalPnl != null ? `${totalPnl >= 0 ? '+' : ''}${Number(totalPnl).toFixed(2)} USDT` : '—'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function DefensePanel({ data }) {
  const positions = (data?.positions ?? []).filter((p) => Number(p.amount) > 0)
  const slotSize = (data?.balance ?? 0) / 10
  const engineOn = data?.engineRunning
  const breakevenMult = data?.settings?.breakevenMult ?? 1.002
  const defPositions = positions.filter((p) => p.leverage === 4)

  return (
    <div className="panel panel-defense">
      <div className="panel-head">
        <span className="panel-title">Savunma Paneli</span>
        <span className={`engine-badge ${engineOn ? 'on' : 'off'}`}>
          {engineOn ? 'Motor AKTİF' : 'Motor PASİF'}
        </span>
      </div>

      <div className="panel-body def-scroll">
        {defPositions.length === 0 ? (
          <p className="empty-state sm">4x defanslı pozisyon yok</p>
        ) : (
          defPositions.map((p) => (
            <DefenseMiniCard
              key={p.posKey}
              pos={p}
              slotSize={slotSize}
              breakevenMult={breakevenMult}
            />
          ))
        )}

        {positions.filter((p) => p.leverage !== 4).map((p) => (
          <DefenseMiniCard
            key={p.posKey}
            pos={p}
            slotSize={slotSize}
            breakevenMult={breakevenMult}
          />
        ))}

        <DerrSummary data={data} />
      </div>
    </div>
  )
}
