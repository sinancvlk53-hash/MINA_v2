import React, { useRef, useEffect, useState } from 'react'
import { fmt, defenseStageLabel, calcDefense } from '../utils/trading.js'
import PositionChartEmbed from './PositionChartEmbed.jsx'
import ChartBottomSheet from './ChartBottomSheet.jsx'
import useMediaQuery from '../hooks/useMediaQuery.js'

function PnlValue({ value, className = '' }) {
  const prev = useRef(value)
  const ref = useRef(null)

  useEffect(() => {
    if (prev.current !== value && ref.current) {
      ref.current.classList.remove('pnl-flash-up', 'pnl-flash-down')
      void ref.current.offsetWidth
      ref.current.classList.add(value >= 0 ? 'pnl-flash-up' : 'pnl-flash-down')
      prev.current = value
    }
  }, [value])

  const positive = value >= 0
  return (
    <span ref={ref} className={`pnl-cell ${positive ? 'text-green' : 'text-red'} ${className}`}>
      {positive ? '+' : ''}{fmt(value, 2)}
    </span>
  )
}

function PnlCell({ value }) {
  return (
    <td className="pnl-cell-wrap">
      <PnlValue value={value} />
    </td>
  )
}

function DefenseBars({ pos, slotSize }) {
  const def = calcDefense(pos, slotSize)
  if (!def || pos.leverage !== 4) return null

  const bars = [
    { key: 'D1', price: def.d1Price, cls: 'def-bar-d1' },
    { key: 'D2', price: def.d2Price, cls: 'def-bar-d2' },
    { key: 'D3', price: def.d3Price, cls: 'def-bar-d3' },
  ]

  return (
    <div className="pos-card-def-bars">
      {bars.map(({ key, price, cls }) => (
        <div key={key} className={`def-bar ${cls}`}>
          <span className="def-bar-tag">{key}</span>
          <span className="def-bar-line" />
          <span className="def-bar-price mono">${fmt(price, 4)}</span>
        </div>
      ))}
    </div>
  )
}

function avgPrice(p) {
  return p.avgPrice ?? p.weightedAvg ?? p.entryPrice
}

function notionalUsdt(p) {
  const mark = p.markPrice ?? p.entryPrice
  return (p.amount ?? 0) * mark
}

export default function PositionTable({
  positions = [],
  onDetail,
  onClose,
  sendMessage,
  slotSize = 0,
  mobileMode = false,
  onSelectPos,
  chartSheetOpen = false,
  onChartSheetChange,
  showInlineChart = true,
}) {
  const isMobile = useMediaQuery('(max-width: 768px)')
  const mobile = mobileMode || isMobile
  const [selected, setSelected] = useState(null)
  const [localSheetOpen, setLocalSheetOpen] = useState(false)

  const sheetOpen = onChartSheetChange ? chartSheetOpen : localSheetOpen

  function setSheetOpen(open) {
    if (onChartSheetChange) onChartSheetChange(open)
    else setLocalSheetOpen(open)
  }

  useEffect(() => {
    if (!positions.length) {
      setSelected(null)
      return
    }
    if (selected && !positions.find((p) => p.posKey === selected.posKey || p.symbol === selected.symbol)) {
      const next = positions[0]
      setSelected(next)
      onSelectPos?.(next)
    }
  }, [positions, selected, onSelectPos])

  if (!positions.length) {
    return (
      <div className="panel panel-positions">
        <div className="panel-head">
          <span className="panel-title">Pozisyonlar</span>
          <span className="panel-badge">0</span>
        </div>
        <div className="empty-state">Açık pozisyon yok</div>
      </div>
    )
  }

  function selectPos(p) {
    setSelected(p)
    onSelectPos?.(p)
  }

  function handleClose(p, e) {
    e?.stopPropagation()
    if (sendMessage) {
      sendMessage({ action: 'close_position', symbol: p.symbol, side: p.side })
    }
    onClose?.(p)
  }

  function handleDetail(p, e) {
    e?.stopPropagation()
    onDetail?.(p)
  }

  function handleRowClick(p) {
    selectPos(p)
    if (mobile) {
      setSheetOpen(true)
    }
  }

  const chartPos = selected ?? positions[0]

  if (mobile) {
    return (
      <>
        <div className="panel panel-positions panel-positions-mobile">
          <div className="panel-head">
            <span className="panel-title">Pozisyonlar</span>
            <span className="panel-badge">{positions.length}</span>
          </div>
          <div className="pos-cards">
            {positions.map((p) => {
              const isLong = p.side === 'LONG'
              const stage = defenseStageLabel(p.defenseLevel || 0)
              const roePositive = p.roe >= 0
              const isSelected =
                (selected?.posKey && selected.posKey === p.posKey) ||
                (selected?.symbol === p.symbol && selected?.side === p.side)

              return (
                <article
                  key={p.posKey || `${p.symbol}_${p.side}`}
                  className={`pos-card ${isSelected ? 'pos-card-selected' : ''}`}
                  onClick={() => handleRowClick(p)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="pos-card-top">
                    <div className="pos-card-symbol">
                      <span className="sym-name">{p.symbol.replace(/USDT$/, '')}</span>
                      <span className="sym-pair">/USDT</span>
                    </div>
                    <div className="pos-card-badges">
                      <span className={`badge-pill ${isLong ? 'badge-pill-long' : 'badge-pill-short'}`}>
                        {p.side}
                      </span>
                      <span className="badge-lev">{p.leverage}x</span>
                      {p.leverage === 4 && (
                        <span className={`def-stage ${stage.cls}`}>{stage.text}</span>
                      )}
                    </div>
                  </div>

                  <div className="pos-card-pnl-row">
                    <div className="pos-card-metric">
                      <span className="pos-card-metric-label">PnL (USDT)</span>
                      <PnlValue value={p.pnlUSDT} className="pos-card-pnl-big" />
                    </div>
                    <div className="pos-card-metric pos-card-metric-right">
                      <span className="pos-card-metric-label">ROE</span>
                      <span className={`pos-card-roe-big mono ${roePositive ? 'text-green' : 'text-red'}`}>
                        {roePositive ? '+' : ''}{fmt(p.roe, 1)}%
                      </span>
                    </div>
                  </div>

                  <div className="pos-card-grid">
                    <div><span className="pos-card-k">Giriş</span><span className="mono">${fmt(p.entryPrice)}</span></div>
                    <div><span className="pos-card-k">Ort.</span><span className="mono">${fmt(avgPrice(p))}</span></div>
                    <div><span className="pos-card-k">Mark</span><span className="mono">${fmt(p.markPrice)}</span></div>
                    <div><span className="pos-card-k">Liq</span><span className="mono liq">${fmt(p.liqPrice)}</span></div>
                    <div><span className="pos-card-k">Miktar</span><span className="mono">{fmt(p.amount, 4)}</span></div>
                    <div><span className="pos-card-k">Büyüklük</span><span className="mono">{fmt(notionalUsdt(p), 2)}</span></div>
                    <div><span className="pos-card-k">Marjin</span><span className="mono">{fmt(p.margin, 2)}</span></div>
                  </div>

                  <DefenseBars pos={p} slotSize={slotSize} />

                  <div className="pos-card-actions">
                    <button type="button" className="btn btn-ghost touch-target" onClick={(e) => handleDetail(p, e)}>
                      Detay
                    </button>
                    <button type="button" className="btn btn-close touch-target" onClick={(e) => handleClose(p, e)}>
                      Kapat
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </div>

        {sheetOpen && chartPos && (
          <ChartBottomSheet
            pos={chartPos}
            slotSize={slotSize}
            onClose={() => setSheetOpen(false)}
          />
        )}
      </>
    )
  }

  return (
    <>
      <div className="panel panel-positions">
        <div className="panel-head">
          <span className="panel-title">Pozisyonlar</span>
          <span className="panel-badge">{positions.length}</span>
          <span className="field-hint" style={{ marginLeft: 'auto', marginTop: 0 }}>
            Grafik için satıra tıkla
          </span>
        </div>
        <div className="table-scroll">
          <table className="pos-table pos-table-wide">
            <thead>
              <tr>
                <th>Sembol</th>
                <th>Yön</th>
                <th>Kaldıraç</th>
                <th>Giriş Fiyatı</th>
                <th>Ortalama Fiyat</th>
                <th>Mark Fiyat</th>
                <th>Likidasyon</th>
                <th>Miktar</th>
                <th>Büyüklük</th>
                <th>Marjin</th>
                <th>ROE %</th>
                <th>PnL</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const isLong = p.side === 'LONG'
                const stage = defenseStageLabel(p.defenseLevel || 0)
                const roePositive = p.roe >= 0
                const isSelected =
                  (selected?.posKey && selected.posKey === p.posKey) ||
                  (selected?.symbol === p.symbol && selected?.side === p.side) ||
                  (!selected && p === positions[0])

                return (
                  <tr
                    key={p.posKey || `${p.symbol}_${p.side}`}
                    className={isSelected ? 'row-selected' : ''}
                    onClick={() => handleRowClick(p)}
                  >
                    <td className="sym-cell">
                      <span className="sym-name">{p.symbol.replace(/USDT$/, '')}</span>
                      <span className="sym-pair">/USDT</span>
                    </td>
                    <td>
                      <span className={`badge ${isLong ? 'badge-long' : 'badge-short'}`}>
                        {p.side}
                      </span>
                    </td>
                    <td className="mono">{p.leverage}x</td>
                    <td className="mono dim">${fmt(p.entryPrice)}</td>
                    <td className="mono">${fmt(avgPrice(p))}</td>
                    <td className="mono">${fmt(p.markPrice)}</td>
                    <td className="mono liq">${fmt(p.liqPrice)}</td>
                    <td className="mono">{fmt(p.amount, 4)}</td>
                    <td className="mono">{fmt(notionalUsdt(p), 2)}</td>
                    <td className="mono">{fmt(p.margin, 2)}</td>
                    <td className={`mono ${roePositive ? 'text-green' : 'text-red'}`}>
                      {roePositive ? '+' : ''}{fmt(p.roe, 1)}%
                    </td>
                    <PnlCell value={p.pnlUSDT} />
                    <td className="actions-cell">
                      <button type="button" className="btn btn-sm btn-ghost" onClick={(e) => handleDetail(p, e)}>
                        Detay
                      </button>
                      <button type="button" className="btn btn-sm btn-close" onClick={(e) => handleClose(p, e)}>
                        Kapat
                      </button>
                      {p.leverage === 4 && (
                        <span className={`def-stage ${stage.cls}`}>{stage.text}</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {showInlineChart && chartPos && (
        <PositionChartEmbed pos={chartPos} slotSize={slotSize} />
      )}
    </>
  )
}
