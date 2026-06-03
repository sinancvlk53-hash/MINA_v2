import React, { useState } from 'react'

export default function CopyTradeConfig() {
  const [mode, setMode] = useState('PERCENTAGE')
  const [value, setValue] = useState(50)
  const isPercent = mode === 'PERCENTAGE'

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Copy Trade</span>
        <span className="panel-badge">v1.1</span>
      </div>
      <div className="panel-body">
        <div className="toggle-row">
          {[['PERCENTAGE', '% ORAN'], ['FIXED_SLOT', 'SABİT SLOT']].map(([m, label]) => (
            <button
              key={m}
              type="button"
              className={`toggle-btn sm ${mode === m ? 'active' : ''}`}
              onClick={() => setMode(m)}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="field-label">{isPercent ? 'Master Slot Oranı' : 'Sabit Miktar'}</label>
        <input
          type="range"
          min={isPercent ? 10 : 10}
          max={isPercent ? 100 : 500}
          step={isPercent ? 5 : 10}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
          style={{ width: '100%', accentColor: '#f0b90b' }}
        />
        <div className="slot-budget-row">
          <span>Değer</span>
          <strong>{isPercent ? `${value}%` : `${value} USDT`}</strong>
        </div>
        <div className="slot-budget-row">
          <span>Bağlı Takipçi</span>
          <strong>0 / 3</strong>
        </div>
      </div>
    </div>
  )
}
