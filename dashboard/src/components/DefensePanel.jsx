import React from 'react'

const DEF_RULES = [
  { level: 1, label: 'D1', trigger: 'ROE ≤ -20%',  color: '#f59e0b', amount: 'slot×0.20' },
  { level: 2, label: 'D2', trigger: 'Fiyat -%12',  color: '#ef4444', amount: 'slot×0.20' },
  { level: 3, label: 'D3', trigger: 'Fiyat -%25',  color: '#7c3aed', amount: 'slot×0.40' },
]

export default function DefensePanel({ data }) {
  const engineOn  = data?.engineRunning
  const positions = data?.positions ?? []

  const counts = { 1: 0, 2: 0, 3: 0 }
  positions.forEach(p => {
    if (p.defenseLevel >= 1) counts[1]++
    if (p.defenseLevel >= 2) counts[2]++
    if (p.defenseLevel >= 3) counts[3]++
  })

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Defense Panel</span>
      </div>

      <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>

        {/* Engine durumu */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-mute)', fontSize: 11 }}>Execution Engine</span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
            background: engineOn ? '#10b98118' : '#ef444418',
            color: engineOn ? 'var(--green)' : 'var(--red)',
            border: '1px solid ' + (engineOn ? '#10b98140' : '#ef444440')
          }}>
            {engineOn === true ? 'AKTİF' : engineOn === false ? 'PASİF' : '—'}
          </span>
        </div>

        {/* SFP Detector */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-mute)', fontSize: 11 }}>SFP Detector</span>
          <span style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
            background: '#f59e0b12', color: 'var(--amber)', border: '1px solid #f59e0b30'
          }}>BEKLEMEDE</span>
        </div>

        {/* Savunma seviyeleri tablosu */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 2 }}>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 7 }}>
            AKTİF SAVUNMALAR
          </div>
          {DEF_RULES.map(({ level, label, trigger, color, amount }) => {
            const cnt = counts[level]
            return (
              <div key={level} style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6
              }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 5,
                  background: cnt > 0 ? color + '22' : '#0f1824',
                  border: '1px solid ' + (cnt > 0 ? color + '55' : '#1c2a3a'),
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: cnt > 0 ? color : '#2d4a63', fontSize: 9, fontWeight: 800,
                  flexShrink: 0
                }}>{label}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: 'var(--text-mute)', fontSize: 10 }}>{trigger}</div>
                  <div style={{ color: '#2d4a63', fontSize: 9 }}>{amount}</div>
                </div>
                <div style={{
                  color: cnt > 0 ? color : 'var(--text-mute)',
                  fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700, minWidth: 16,
                  textAlign: 'right'
                }}>{cnt}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
