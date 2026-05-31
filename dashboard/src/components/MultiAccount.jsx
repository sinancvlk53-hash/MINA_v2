import React from 'react'

const ACCOUNTS = [
  { id: 'master', label: 'Master Hesap', sub: 'Aktif',         active: true  },
  { id: 'f1',     label: 'Follower 1',   sub: 'Boş — yakında', active: false },
  { id: 'f2',     label: 'Follower 2',   sub: 'Boş — yakında', active: false },
  { id: 'f3',     label: 'Follower 3',   sub: 'Boş — yakında', active: false },
]

export default function MultiAccount() {
  return (
    <div className="section-card" style={{ minWidth: 240 }}>
      <div className="section-header">
        <span className="section-title">Hesaplar</span>
      </div>
      <div className="account-list">
        {ACCOUNTS.map((acc, i) => (
          <div
            key={acc.id}
            className="account-item"
            style={{
              opacity: acc.active ? 1 : 0.4,
              borderBottom: i < ACCOUNTS.length - 1 ? '1px solid #0f172a' : 'none'
            }}
          >
            <div
              className="account-dot"
              style={{
                background: acc.active ? 'var(--green)' : '#334155',
                boxShadow: acc.active ? '0 0 6px var(--green)' : 'none',
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{
                color: acc.active ? 'var(--text)' : 'var(--text-mute)',
                fontSize: 13, fontWeight: 600
              }}>{acc.label}</div>
              <div style={{ color: 'var(--text-mute)', fontSize: 11 }}>{acc.sub}</div>
            </div>
            {!acc.active && (
              <span style={{
                padding: '2px 6px',
                background: '#1e293b',
                borderRadius: 4,
                color: 'var(--text-mute)',
                fontSize: 9,
                fontWeight: 700,
                letterSpacing: 0.5
              }}>SOON</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
