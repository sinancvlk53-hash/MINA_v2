import React, { useState } from 'react'

export default function CopyTradeConfig() {
  const [mode, setMode]   = useState('PERCENTAGE')
  const [value, setValue] = useState(50)

  const isPercent = mode === 'PERCENTAGE'

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Copy Trade Config</span>
        <span style={{
          marginLeft: 'auto', padding: '1px 6px',
          background: '#f59e0b18', color: 'var(--amber)',
          borderRadius: 3, fontSize: 8, fontWeight: 700
        }}>v1.1 HAZIRLIK</span>
      </div>

      <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Mod seçimi */}
        <div>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 5 }}>
            DAĞITIM MODU
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            {[['PERCENTAGE', '% ORAN'], ['FIXED_SLOT', 'SABİT SLOT']].map(([m, label]) => (
              <button key={m} onClick={() => setMode(m)} style={{
                flex: 1, padding: '5px 6px', borderRadius: 5,
                border: '1px solid ' + (mode === m ? 'var(--accent)' : 'var(--border)'),
                background: mode === m ? '#3b82f618' : 'transparent',
                color: mode === m ? 'var(--accent)' : 'var(--text-mute)',
                fontSize: 9, fontWeight: 700, cursor: 'pointer', letterSpacing: .3
              }}>{label}</button>
            ))}
          </div>
        </div>

        {/* Değer ayarı */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5 }}>
              {isPercent ? 'MASTER SLOT ORANI' : 'SABİT MIKTAR'}
            </span>
            <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700 }}>
              {isPercent ? value + '%' : value + ' $'}
            </span>
          </div>
          <input
            type="range"
            min={isPercent ? 10 : 10}
            max={isPercent ? 100 : 500}
            step={isPercent ? 5 : 10}
            value={value}
            onChange={e => setValue(Number(e.target.value))}
          />
        </div>

        {/* Takipçi durumu */}
        <div style={{
          paddingTop: 8, borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <span style={{ color: 'var(--text-mute)', fontSize: 11 }}>Bağlı Takipçi</span>
          <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700 }}>
            0 / 3
          </span>
        </div>
      </div>
    </div>
  )
}
