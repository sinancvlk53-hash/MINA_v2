import React from 'react'

const DEF_COLORS = ['#f59e0b', '#ef4444', '#7c3aed']

function DefenseBadges({ level }) {
  return (
    <div className="def-badges">
      {[1, 2, 3].map(l => (
        <div key={l} className="def-badge" style={
          l <= level
            ? { background: DEF_COLORS[l - 1] + '28', border: '1px solid ' + DEF_COLORS[l - 1] + '66', color: DEF_COLORS[l - 1] }
            : { background: '#0f1824', border: '1px solid #1c2a3a', color: '#2d4a63' }
        }>D{l}</div>
      ))}
    </div>
  )
}

function fmt(n, d = 4) {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(d)
}

export default function PositionTable({ positions, selected, onSelect }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="section-card">
        <div className="section-header">
          <span className="section-title">Pozisyonlar (0)</span>
        </div>
        <div style={{
          padding: '40px 20px', textAlign: 'center',
          color: 'var(--text-mute)', fontSize: 12
        }}>Açık pozisyon yok</div>
      </div>
    )
  }

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Pozisyonlar ({positions.length})</span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-mute)', fontSize: 9 }}>
          Grafik için satıra tıkla
        </span>
      </div>
      <div className="pos-table-wrap">
        <table className="pos-table">
          <thead>
            <tr>
              <th>Coin</th>
              <th>Yön</th>
              <th>Giriş</th>
              <th>Mark</th>
              <th>PnL (USDT)</th>
              <th>ROE %</th>
              <th>Savunma</th>
              <th>Likidasyon</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p, i) => {
              const isLong = p.side === 'LONG'
              const pnlC   = p.pnlUSDT >= 0 ? 'var(--green)' : 'var(--red)'
              const roeC   = p.roe    >= 0 ? 'var(--green)' : 'var(--red)'
              const isSelected = selected === p.symbol

              return (
                <tr
                  key={p.posKey || i}
                  className={isSelected ? 'selected' : ''}
                  onClick={() => onSelect && onSelect(p.symbol)}
                >
                  <td>
                    <span style={{ color: 'var(--text)', fontWeight: 700, fontSize: 12 }}>
                      {p.symbol.replace(/USDT$/, '')}
                    </span>
                    <span style={{ color: 'var(--text-mute)', fontSize: 10 }}>/USDT</span>
                  </td>
                  <td>
                    <span style={{
                      padding: '2px 7px', borderRadius: 4,
                      background: isLong ? '#10b98118' : '#ef444418',
                      color: isLong ? 'var(--green)' : 'var(--red)',
                      fontSize: 10, fontWeight: 700
                    }}>{p.side}</span>
                  </td>
                  <td style={{ color: 'var(--text-mute)', fontFamily: 'var(--mono)', fontSize: 11 }}>
                    ${fmt(p.entryPrice)}
                  </td>
                  <td style={{ color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 11 }}>
                    ${fmt(p.markPrice)}
                  </td>
                  <td style={{ color: pnlC, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600 }}>
                    {p.pnlUSDT >= 0 ? '+' : ''}{fmt(p.pnlUSDT, 2)}
                  </td>
                  <td style={{ color: roeC, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600 }}>
                    {p.roe >= 0 ? '+' : ''}{fmt(p.roe, 1)}%
                  </td>
                  <td><DefenseBadges level={p.defenseLevel || 0} /></td>
                  <td style={{ color: '#ef4444aa', fontFamily: 'var(--mono)', fontSize: 11 }}>
                    ${fmt(p.liqPrice)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
