import React, { useRef, useEffect, useState } from 'react'
import { fmt, defenseStageLabel, calcDefense, resolveStrategyMode } from '../utils/trading.js'
import ChartFullscreenModal from './ChartFullscreenModal.jsx'
import ClosePositionConfirm from './ClosePositionConfirm.jsx'
import ManualOverrideControls from './ManualOverrideControls.jsx'
import useMediaQuery from '../hooks/useMediaQuery.js'

function SideBadge({ side }) {
  const isLong = side === 'LONG'
  return (
    <span className={`side-badge ${isLong ? 'side-badge-long' : 'side-badge-short'}`} title={side}>
      {isLong ? 'L' : 'S'}
    </span>
  )
}

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

function SourceBadge({ source, label }) {
  if (!source) return null
  const cls = source === 'HT' ? 'badge-src-ht' : source === 'MZ' ? 'badge-src-mz' : 'badge-src-manuel'
  return (
    <span className={`badge-pill badge-src ${cls}`} title={label || source}>
      {source}
    </span>
  )
}

function StrategyBadge({ mode }) {
  const stratMode = mode || 'defense'
  const labels = {
    defense: 'Savunma',
    stop: 'Stop',
    ht: 'HT',
    full_manual: 'Manuel',
  }
  const clsMap = {
    defense: 'badge-strategy-defense',
    stop: 'badge-strategy-stop',
    ht: 'badge-strategy-ht',
    ht_pdf: 'badge-strategy-ht-pdf',
    full_manual: 'badge-strategy-manual',
  }
  const label = labels[stratMode] || stratMode
  const cls = clsMap[stratMode] || 'badge-strategy-defense'
  return (
    <span className={`badge-pill ${cls}`} title={`Strateji: ${label}`}>
      {label}
    </span>
  )
}

function MerterEmptySlot({ slot }) {
  if (!slot) return null
  const filterBadge = slot.filterMode === 'unfiltered'
    ? 'Süzgeçsiz'
    : slot.filterMode === 'filtered'
      ? 'Süzgeçli'
      : null
  return (
    <article className="pos-card pos-card-merter-empty">
      <div className="pos-card-top">
        <div className="pos-card-symbol">
          <span className="sym-name merter-slot-label">{slot.label}</span>
        </div>
        <span className="badge-pill badge-merter-idle">BOŞ</span>
      </div>
      {filterBadge && (
        <span className={`badge-pill ${slot.filterMode === 'unfiltered' ? 'badge-filter-raw' : 'badge-filter-full'}`}>
          {filterBadge}
        </span>
      )}
      {slot.filterDesc && (
        <p className="merter-empty-hint">{slot.filterDesc}</p>
      )}
      <p className="merter-empty-hint">1x DCA · 10 parça · Sinyal bekleniyor</p>
      <div className="merter-parts-bar">
        <div className="merter-parts-fill" style={{ width: '0%' }} />
      </div>
      <span className="field-hint">0 / {slot.partsTotal ?? 10} parça</span>
    </article>
  )
}

function MerterOccupiedMeta({ pos, slotMeta }) {
  const filled = slotMeta?.partsFilled ?? pos.partsFilled ?? 0
  const total = slotMeta?.partsTotal ?? 10
  const pct = total > 0 ? (filled / total) * 100 : 0
  return (
    <div className="merter-meta">
      <span className="badge-pill badge-merter-active">{slotMeta?.label ?? 'Merter'}</span>
      {slotMeta?.filterMode && (
        <span className={`badge-pill ${slotMeta.filterMode === 'unfiltered' ? 'badge-filter-raw' : 'badge-filter-full'}`}>
          {slotMeta.filterMode === 'unfiltered' ? 'Süzgeçsiz' : 'Süzgeçli'}
        </span>
      )}
      {slotMeta?.breakevenMode && (
        <span className="badge-pill badge-breakeven">BE modu</span>
      )}
      <div className="merter-parts-bar">
        <div className="merter-parts-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="field-hint">{filled} / {total} parça</span>
    </div>
  )
}

function PositionCards({
  positions,
  slotSize,
  mobile,
  selected,
  onRowClick,
  onDetail,
  onClose,
  sendMessage,
  merterSlots,
  isMerterSection,
  leverageStrategy = {},
}) {
  return (
    <div className="pos-cards">
      {positions.map((p) => {
        const stage = defenseStageLabel(p.defenseLevel || 0)
        const roePositive = p.roe >= 0
        const isSelected =
          (selected?.posKey && selected.posKey === p.posKey) ||
          (selected?.symbol === p.symbol && selected?.side === p.side)
        const slotMeta = p.merterYuva ? merterSlots?.[p.merterYuva] : null
        const manualActive = p.manualOverride?.active
        const stratMode = p.strategyMode || resolveStrategyMode(p.leverage, leverageStrategy)

        return (
          <article
            key={p.posKey || `${p.symbol}_${p.side}`}
            className={`pos-card ${isMerterSection ? 'pos-card-merter' : ''} ${isSelected ? 'pos-card-selected' : ''} ${manualActive ? 'pos-card-manual-active' : ''}`}
            onClick={() => onRowClick(p)}
            role="button"
            tabIndex={0}
          >
            <div className="pos-card-top">
              <div className="pos-card-symbol">
                <span className="sym-name">{p.symbol.replace(/USDT$/, '')}</span>
                <span className="sym-pair">/USDT</span>
              </div>
              <div className="pos-card-badges">
                <SideBadge side={p.side} />
                <SourceBadge source={p.signalSource} label={p.signalSourceLabel} />
                <span className="badge-lev">{p.leverage}x</span>
                <StrategyBadge mode={stratMode} />
                {p.leverage === 4 && (
                  <span className={`def-stage ${stage.cls}`}>{stage.text}</span>
                )}
              </div>
            </div>

            {isMerterSection && <MerterOccupiedMeta pos={p} slotMeta={slotMeta} />}

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
              <div><span className="pos-card-k">Piyasa Fiyatı</span><span className="mono">${fmt(p.markPrice)}</span></div>
              <div><span className="pos-card-k">Liq</span><span className="mono liq">${fmt(p.liqPrice)}</span></div>
              <div><span className="pos-card-k">Miktar</span><span className="mono">{fmt(p.amount, 4)}</span></div>
              <div><span className="pos-card-k">Büyüklük</span><span className="mono">{fmt(notionalUsdt(p), 2)}</span></div>
              <div><span className="pos-card-k">Marjin</span><span className="mono">{fmt(p.margin, 2)}</span></div>
            </div>

            <DefenseBars pos={p} slotSize={slotSize} />

            <ManualOverrideControls pos={p} sendMessage={sendMessage} />

            <div className="pos-card-actions">
              <button type="button" className="btn btn-ghost touch-target" onClick={(e) => { e.stopPropagation(); onDetail?.(p) }}>
                Detay
              </button>
              <button type="button" className="btn btn-close touch-target" onClick={(e) => { e.stopPropagation(); onClose?.(p, e, sendMessage) }}>
                Kapat
              </button>
            </div>
          </article>
        )
      })}
    </div>
  )
}

function PositionTableDesktop({
  positions,
  slotSize,
  selected,
  onRowClick,
  onDetail,
  onClose,
  sendMessage,
  merterSlots,
  leverageStrategy = {},
}) {
  return (
    <div className="table-scroll">
      <table className="pos-table pos-table-wide">
        <thead>
          <tr>
            <th>Sembol</th>
            <th>Kaynak</th>
            <th>Yön</th>
            <th>Kaldıraç</th>
            <th>Giriş</th>
            <th>Piyasa Fiyatı</th>
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
              (selected?.symbol === p.symbol && selected?.side === p.side)
            const stratMode = p.strategyMode || resolveStrategyMode(p.leverage, leverageStrategy)
            const slotMeta = p.merterYuva ? merterSlots?.[p.merterYuva] : null
            const partsFilled = slotMeta?.partsFilled ?? p.partsFilled
            const partsTotal = slotMeta?.partsTotal ?? p.partsTotal ?? 10

            return (
              <tr
                key={p.posKey || `${p.symbol}_${p.side}`}
                className={`${isSelected ? 'row-selected' : ''} ${p.slotType === 'merter' ? 'row-merter' : ''} ${p.manualOverride?.active ? 'row-manual-active' : ''}`}
                onClick={() => onRowClick(p)}
              >
                <td className="sym-cell">
                  <span className="sym-name">{p.symbol.replace(/USDT$/, '')}</span>
                  <span className="sym-pair">/USDT</span>
                  {p.slotType === 'merter' && partsFilled != null && (
                    <span className="field-hint merter-parts-inline">{partsFilled}/{partsTotal} parça</span>
                  )}
                </td>
                <td>
                  <SourceBadge source={p.signalSource} label={p.signalSourceLabel} />
                </td>
                <td>
                  <SideBadge side={p.side} />
                </td>
                <td className="mono">
                  {p.leverage}x
                  <StrategyBadge mode={stratMode} />
                </td>
                <td className="mono dim">${fmt(p.entryPrice)}</td>
                <td className="mono">${fmt(p.markPrice)}</td>
                <td className={`mono ${roePositive ? 'text-green' : 'text-red'}`}>
                  {roePositive ? '+' : ''}{fmt(p.roe, 1)}%
                </td>
                <PnlCell value={p.pnlUSDT} />
                <td className="actions-cell">
                  <ManualOverrideControls pos={p} sendMessage={sendMessage} />
                  <button type="button" className="btn btn-sm btn-ghost" onClick={(e) => { e.stopPropagation(); onDetail?.(p) }}>Detay</button>
                  <button type="button" className="btn btn-sm btn-close" onClick={(e) => { e.stopPropagation(); onClose?.(p, e, sendMessage) }}>Kapat</button>
                  {p.leverage === 4 && <span className={`def-stage ${stage.cls}`}>{stage.text}</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function PositionSection({
  title,
  subtitle,
  badge,
  positions,
  emptyText,
  merterSlots,
  isMerterSection,
  mobile,
  slotSize,
  selected,
  onRowClick,
  onDetail,
  onClose,
  sendMessage,
  showTable,
  leverageStrategy = {},
}) {
  const emptyMerter = isMerterSection && merterSlots
    ? Object.keys(merterSlots).filter((k) => !merterSlots[k]?.occupied)
    : []

  return (
    <div className={`panel panel-positions ${isMerterSection ? 'panel-merter' : 'panel-motor'}`}>
      <div className="panel-head">
        <div>
          <span className="panel-title">{title}</span>
          {subtitle && <span className="panel-subtitle">{subtitle}</span>}
        </div>
        <span className={`panel-badge ${isMerterSection ? 'badge-merter-count' : ''}`}>{badge}</span>
      </div>

      {!positions.length && !emptyMerter.length ? (
        <div className="empty-state">{emptyText}</div>
      ) : mobile ? (
        <>
          <PositionCards
            positions={positions}
            slotSize={slotSize}
            mobile={mobile}
            selected={selected}
            onRowClick={onRowClick}
            onDetail={onDetail}
            onClose={onClose}
            sendMessage={sendMessage}
            merterSlots={merterSlots}
            isMerterSection={isMerterSection}
            leverageStrategy={leverageStrategy}
          />
          {emptyMerter.map((k) => (
            <MerterEmptySlot key={k} slot={merterSlots[k]} />
          ))}
        </>
      ) : (
        <>
          {emptyMerter.map((k) => (
            <MerterEmptySlot key={k} slot={merterSlots[k]} />
          ))}
          {positions.length > 0 && (
            <PositionTableDesktop
              positions={positions}
              slotSize={slotSize}
              selected={selected}
              onRowClick={onRowClick}
              onDetail={onDetail}
              onClose={onClose}
              sendMessage={sendMessage}
              merterSlots={merterSlots}
              leverageStrategy={leverageStrategy}
            />
          )}
        </>
      )}
    </div>
  )
}

export default function PositionTable({
  motorPositions = [],
  merterPositions = [],
  merterSlots = {},
  positions: legacyPositions,
  onDetail,
  onClose,
  sendMessage,
  slotSize = 0,
  mobileMode = false,
  onSelectPos,
  selectedPos,
  chartSheetOpen = false,
  onChartSheetChange,
  leverageStrategy = {},
  onOpenPositions,
}) {
  const isMobile = useMediaQuery('(max-width: 768px)')
  const mobile = mobileMode || isMobile
  const [selected, setSelected] = useState(null)
  const [localSheetOpen, setLocalSheetOpen] = useState(false)
  const [closeTarget, setCloseTarget] = useState(null)

  const motor = motorPositions.length ? motorPositions : (legacyPositions ?? []).filter((p) => p.slotType !== 'merter')
  const merter = merterPositions.length ? merterPositions : (legacyPositions ?? []).filter((p) => p.slotType === 'merter')
  const allPositions = [...motor, ...merter]

  const sheetOpen = onChartSheetChange ? chartSheetOpen : localSheetOpen

  function setSheetOpen(open) {
    if (onChartSheetChange) onChartSheetChange(open)
    else setLocalSheetOpen(open)
  }

  useEffect(() => {
    if (!allPositions.length) {
      setSelected(null)
      return
    }
    if (selected && !allPositions.find((p) => p.posKey === selected.posKey || (p.symbol === selected.symbol && p.side === selected.side))) {
      const next = allPositions[0]
      setSelected(next)
      onSelectPos?.(next)
    }
  }, [allPositions, selected, onSelectPos, motor, merter])

  function selectPos(p) {
    setSelected(p)
    onSelectPos?.(p)
  }

  function handleCloseRequest(p, e) {
    e?.stopPropagation()
    setCloseTarget(p)
  }

  function confirmClosePosition() {
    if (closeTarget && sendMessage) {
      sendMessage({
        action: 'close_position',
        symbol: closeTarget.symbol,
        side: closeTarget.side,
      })
    }
    setCloseTarget(null)
  }

  function handleClose(p, e, msgFn) {
    handleCloseRequest(p, e)
  }

  function handleRowClick(p) {
    selectPos(p)
    setSheetOpen(true)
  }

  const chartPos = (selectedPos ?? selected) || allPositions[0]
  const common = {
    mobile,
    slotSize,
    selected,
    onRowClick: handleRowClick,
    onDetail,
    onClose: handleClose,
    sendMessage,
    leverageStrategy,
  }

  if (!allPositions.length && !Object.keys(merterSlots).length) {
    return (
      <div className="panel panel-positions">
        <div className="panel-head">
          <span
            className="panel-title panel-title-btn"
            role="button"
            tabIndex={0}
            onClick={() => onOpenPositions?.()}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onOpenPositions?.() }}
          >
            Pozisyonlar
          </span>
          <span className="panel-badge">0</span>
        </div>
        <div className="empty-state">Açık pozisyon yok</div>
      </div>
    )
  }

  if (mobile) {
    return (
      <>
        <div className="positions-stack">
          <PositionSection
            title="4x Motor"
            subtitle="Ana slotlar (max 8)"
            badge={motor.length}
            positions={motor}
            emptyText="Motor pozisyonu yok"
            isMerterSection={false}
            {...common}
          />
          <PositionSection
            title="Merter 1x DCA"
            subtitle="EI süzgeçli + süzgeçsiz + RSI"
            badge={`${merter.length}/${Object.keys(merterSlots).length || 3}`}
            positions={merter}
            emptyText=""
            merterSlots={merterSlots}
            isMerterSection
            {...common}
          />
        </div>
        {sheetOpen && chartPos && (
          <ChartFullscreenModal
            pos={chartPos}
            slotSize={slotSize}
            onClose={() => setSheetOpen(false)}
          />
        )}
        <ClosePositionConfirm
          open={!!closeTarget}
          pos={closeTarget}
          onConfirm={confirmClosePosition}
          onCancel={() => setCloseTarget(null)}
        />
      </>
    )
  }

  return (
    <>
      <div className="positions-stack">
        <PositionSection
          title="4x Motor"
          subtitle="Ana slotlar (max 8)"
          badge={motor.length}
          positions={motor}
          emptyText="Motor pozisyonu yok"
          isMerterSection={false}
          showTable
          {...common}
        />
        <PositionSection
          title="Merter 1x DCA"
          subtitle="EI süzgeçli + süzgeçsiz + RSI"
          badge={`${merter.length}/${Object.keys(merterSlots).length || 3}`}
          positions={merter}
          emptyText=""
          merterSlots={merterSlots}
          isMerterSection
          showTable
          {...common}
        />
      </div>
      {sheetOpen && chartPos && (
        <ChartFullscreenModal
          pos={chartPos}
          slotSize={slotSize}
          onClose={() => setSheetOpen(false)}
        />
      )}
      <ClosePositionConfirm
        open={!!closeTarget}
        pos={closeTarget}
        onConfirm={confirmClosePosition}
        onCancel={() => setCloseTarget(null)}
      />
    </>
  )
}
