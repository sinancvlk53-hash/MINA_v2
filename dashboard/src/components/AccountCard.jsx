import React from 'react'

const FOLLOWERS = [
  { id: 'f1', label: 'Follower 1' },
  { id: 'f2', label: 'Follower 2' },
  { id: 'f3', label: 'Follower 3' },
]

/** Hesap slot görselleştirmesi — OrderPanel ile birleştirildi; mantık korundu. */
export default function AccountCard({ data }) {
  const balance = data?.balance
  const posCount = data?.positionCount ?? 0

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Hesaplar</span>
      </div>
      <div className="panel-body">
        <div className="slot-budget-row">
          <span>Master Bakiye</span>
          <strong className="mono">${balance != null ? balance.toFixed(2) : '—'}</strong>
        </div>
        <div className="field-label">Slot ({posCount}/10)</div>
        <div className="slot-bar">
          {Array.from({ length: 10 }, (_, i) => (
            <div key={i} className={`slot-cell ${i < posCount ? 'used' : ''}`} />
          ))}
        </div>
        {FOLLOWERS.map((f) => (
          <div key={f.id} className="def-mini-muted" style={{ marginTop: 8, opacity: 0.5 }}>
            {f.label} — bağlı değil
          </div>
        ))}
      </div>
    </div>
  )
}
