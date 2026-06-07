import React, { useEffect, useState } from 'react'

export default function ManualOverrideControls({ pos, sendMessage }) {
  const mo = pos.manualOverride || {}
  const active = !!mo.active
  const [stop, setStop] = useState(mo.stop != null ? String(mo.stop) : '')
  const [tp, setTp] = useState(mo.tp != null ? String(mo.tp) : '')
  const [expanded, setExpanded] = useState(active)

  useEffect(() => {
    setStop(mo.stop != null ? String(mo.stop) : '')
    setTp(mo.tp != null ? String(mo.tp) : '')
    setExpanded(!!mo.active)
  }, [mo.active, mo.stop, mo.tp, pos.posKey])

  function payload(activeFlag) {
    const stopVal = stop.trim() === '' ? null : parseFloat(stop)
    const tpVal = tp.trim() === '' ? null : parseFloat(tp)
    return {
      action: 'set_manual_override',
      symbol: pos.symbol,
      side: pos.side,
      active: activeFlag,
      stop: Number.isFinite(stopVal) ? stopVal : null,
      tp: Number.isFinite(tpVal) ? tpVal : null,
    }
  }

  function toggleManual(e) {
    e?.stopPropagation()
    if (active) {
      sendMessage?.(payload(false))
    } else {
      setExpanded(true)
      sendMessage?.(payload(true))
    }
  }

  function apply(e) {
    e?.stopPropagation()
    sendMessage?.(payload(true))
  }

  return (
    <div className="manual-override-box" onClick={(e) => e.stopPropagation()}>
      {active && (
        <span className="manual-override-badge">🔶 Manuel Yönetim Aktif</span>
      )}
      {(active || expanded) && (
        <div className="manual-override-fields">
          <label className="manual-override-field">
            <span>Stop</span>
            <input
              className="field-input manual-override-input"
              type="number"
              min="0"
              step="any"
              placeholder="Stop fiyatı"
              value={stop}
              onChange={(e) => setStop(e.target.value)}
            />
          </label>
          <label className="manual-override-field">
            <span>TP</span>
            <input
              className="field-input manual-override-input"
              type="number"
              min="0"
              step="any"
              placeholder="TP fiyatı"
              value={tp}
              onChange={(e) => setTp(e.target.value)}
            />
          </label>
          <button type="button" className="btn btn-sm btn-manual-apply touch-target" onClick={apply}>
            Uygula
          </button>
        </div>
      )}
      <button
        type="button"
        className={`btn btn-sm ${active ? 'btn-manual-off' : 'btn-manual-on'} touch-target`}
        onClick={toggleManual}
      >
        {active ? 'Otomatik Mod' : 'Manuel Yönet'}
      </button>
    </div>
  )
}
