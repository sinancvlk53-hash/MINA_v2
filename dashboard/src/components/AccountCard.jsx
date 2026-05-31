import React from 'react'

const FOLLOWERS = [
  { id: 'f1', label: 'Follower 1' },
  { id: 'f2', label: 'Follower 2' },
  { id: 'f3', label: 'Follower 3' },
]

export default function AccountCard({ data }) {
  const balance  = data?.balance
  const posCount = data?.positionCount ?? 0
  const slots    = Array.from({ length: 10 }, (_, i) => i < posCount)

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Hesaplar</span>
      </div>

      {/* Master */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
            background: 'var(--green)', boxShadow: '0 0 6px var(--green)'
          }} />
          <span style={{ color: 'var(--text)', fontWeight: 700, fontSize: 12 }}>Master Hesap</span>
          <span style={{
            marginLeft: 'auto', color: 'var(--text-dim)',
            fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700
          }}>
            ${balance != null ? balance.toFixed(2) : '—'}
          </span>
        </div>

        {/* Slot görselleştirmesi */}
        <div style={{ marginBottom: 4 }}>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 4 }}>
            SLOT ({posCount}/10)
          </div>
          <div style={{ display: 'flex', gap: 3 }}>
            {slots.map((used, i) => (
              <div key={i} style={{
                flex: 1, height: 7, borderRadius: 2,
                background: used ? 'var(--accent)' : '#1c2a3a',
                boxShadow: used ? '0 0 5px var(--accent)44' : 'none',
                transition: 'background .3s'
              }} />
            ))}
          </div>
        </div>
      </div>

      {/* Follower'lar */}
      {FOLLOWERS.map((f, i) => (
        <div key={f.id} style={{
          padding: '9px 14px',
          borderBottom: i < FOLLOWERS.length - 1 ? '1px solid #0a101a' : 'none',
          display: 'flex', alignItems: 'center', gap: 8, opacity: .38
        }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#2d4a63', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ color: 'var(--text-mute)', fontSize: 11, fontWeight: 600 }}>{f.label}</div>
            <div style={{ color: '#2d4a63', fontSize: 9 }}>Boş — bağlı değil</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ color: '#2d4a63', fontSize: 9, fontFamily: 'var(--mono)' }}>—ms</span>
            <span style={{
              padding: '1px 5px', background: '#0f1824', borderRadius: 3,
              color: '#2d4a63', fontSize: 8, fontWeight: 700
            }}>SOON</span>
          </div>
        </div>
      ))}
    </div>
  )
}
