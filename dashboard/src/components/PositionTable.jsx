import React from 'react'

const DEF_COLORS = ['#F0B90B', '#F6465D', '#7c3aed']

function getLevRules(lev) {
  if (lev === 10) return { tp_type: 'fast', tp1_pct: 2, tp2_pct: 4, tp2_close: 1.00, trailing_callback: null }
  return { tp_type: 'standard', tp1_pct: 3, tp2_pct: 5, tp2_close: 0.50, trailing_callback: 2.0 }
}

function calcTP(pos) {
  const { entryPrice, amount, leverage, side } = pos
  const rules = getLevRules(leverage)
  const { tp1_pct, tp2_pct, tp2_close, trailing_callback, tp_type } = rules
  const dir = side === 'LONG' ? 1 : -1

  const tp1Price = entryPrice * (1 + dir * tp1_pct / 100)
  const tp2Price = entryPrice * (1 + dir * tp2_pct / 100)
  const tp1Qty   = amount * 0.50
  const tp2Qty   = amount * 0.50 * tp2_close
  const tp1Usdt  = (tp1Price - entryPrice) * tp1Qty * dir
  const tp2Usdt  = (tp2Price - entryPrice) * tp2Qty * dir

  return { tp1Price, tp2Price, tp1Usdt, tp2Usdt, trailing_callback, tp_type, tp1_pct, tp2_pct }
}

function DefenseBadges({ level }) {
  return (
    <div className="def-badges">
      {[1, 2, 3].map(l => (
        <div key={l} className="def-badge" style={
          l <= level
            ? { background: DEF_COLORS[l - 1] + '28', border: '1px solid ' + DEF_COLORS[l - 1] + '66', color: DEF_COLORS[l - 1] }
            : { background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-mute)' }
        }>D{l}</div>
      ))}
    </div>
  )
}

function fmt(n, d = 4) {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(d)
}

function TPRow({ pos }) {
  const tp = calcTP(pos)
  const isFast = tp.tp_type === 'fast'
  const green = 'var(--green)'
  const mute  = 'var(--text-mute)'
  const mono  = 'var(--mono)'

  const cellStyle = {
    padding: '8px 12px',
    borderRight: '1px solid var(--border)',
    minWidth: 140,
    verticalAlign: 'top',
  }
  const labelStyle = { fontSize: 9, color: mute, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: 4, fontWeight: 700 }
  const priceStyle = { fontSize: 12, fontFamily: mono, color: 'var(--text)', fontWeight: 600 }
  const usdtStyle  = { fontSize: 11, fontFamily: mono, color: green, fontWeight: 700, marginTop: 2 }
  const noteStyle  = { fontSize: 9, color: mute, marginTop: 2 }

  return (
    <tr>
      <td colSpan={8} style={{ padding: 0, background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
        <div style={{
          display: 'flex', alignItems: 'stretch',
          borderTop: '1px solid var(--border)',
          fontSize: 11,
        }}>
          {/* Etiket */}
          <div style={{ ...cellStyle, background: 'var(--surface)', minWidth: 90, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 9, color: mute, letterSpacing: '0.8px', fontWeight: 700 }}>TP PLANI</div>
              <div style={{ fontSize: 10, color: isFast ? 'var(--amber)' : 'var(--accent)', fontWeight: 700, marginTop: 3 }}>
                {pos.leverage}x {isFast ? 'FAST' : 'STD'}
              </div>
            </div>
          </div>

          {/* TP1 */}
          <div style={cellStyle}>
            <div style={labelStyle}>TP1 (+%{tp.tp1_pct})</div>
            <div style={priceStyle}>${fmt(tp.tp1Price, 4)}</div>
            <div style={usdtStyle}>+{fmt(tp.tp1Usdt, 2)} USDT</div>
            <div style={noteStyle}>Giriş × {(1 + (pos.side === 'LONG' ? 1 : -1) * tp.tp1_pct / 100).toFixed(2)} · %50 kapat</div>
          </div>

          {/* TP2 */}
          <div style={cellStyle}>
            <div style={labelStyle}>TP2 (+%{tp.tp2_pct})</div>
            <div style={priceStyle}>${fmt(tp.tp2Price, 4)}</div>
            <div style={usdtStyle}>+{fmt(tp.tp2Usdt, 2)} USDT</div>
            <div style={noteStyle}>
              {isFast ? 'Kalan %100 kapat' : 'Kalan %50 kapat (%25 toplam)'}
            </div>
          </div>

          {/* Trailing */}
          <div style={{ ...cellStyle, borderRight: 'none' }}>
            <div style={labelStyle}>Trailing Stop</div>
            {isFast ? (
              <>
                <div style={{ fontSize: 12, color: 'var(--red)', fontWeight: 700 }}>YOK</div>
                <div style={noteStyle}>10x TP2 ile pozisyon kapanır</div>
              </>
            ) : (
              <>
                <div style={priceStyle}>Başlangıç: TP2 fiyatı</div>
                <div style={{ fontSize: 11, fontFamily: mono, color: 'var(--amber)', fontWeight: 700, marginTop: 2 }}>
                  callbackRate: %{tp.trailing_callback}
                </div>
                <div style={noteStyle}>TRAILING_STOP_MARKET · Tepeden -%{tp.trailing_callback} düşünce kapanır</div>
              </>
            )}
          </div>

          {/* Giriş referansı */}
          <div style={{ ...cellStyle, borderRight: 'none', marginLeft: 'auto', background: 'var(--surface)', minWidth: 130 }}>
            <div style={labelStyle}>Giriş Fiyatı</div>
            <div style={priceStyle}>${fmt(pos.entryPrice, 4)}</div>
            <div style={noteStyle}>Miktar: {fmt(pos.amount, 4)}</div>
            <div style={{ fontSize: 9, color: mute, marginTop: 2 }}>
              {pos.side === 'LONG' ? '↑ LONG' : '↓ SHORT'}
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}

function DefenseRow({ pos }) {
  if (pos.leverage !== 4) return null

  const { entryPrice, side } = pos
  const isLong = side === 'LONG'
  const mono   = 'var(--mono)'
  const mute   = 'var(--text-mute)'

  const d1Trigger = entryPrice * (isLong ? 0.95 : 1.05)
  const d2Trigger = entryPrice * (isLong ? 0.88 : 1.12)
  // BE hedefi: D2 sonrası ağırlıklı ortalama × 1.0035
  const beTarget  = isLong ? d2Trigger * 1.0035 : d2Trigger * 0.9965

  const cellStyle = {
    padding: '8px 12px',
    borderRight: '1px solid var(--border)',
    minWidth: 150,
    verticalAlign: 'top',
  }
  const labelStyle = {
    fontSize: 9, color: mute, letterSpacing: '0.8px',
    textTransform: 'uppercase', marginBottom: 4, fontWeight: 700,
  }

  return (
    <tr>
      <td colSpan={8} style={{ padding: 0, background: 'var(--bg)', borderBottom: '1px solid var(--border)' }}>
        <div style={{
          display: 'flex', alignItems: 'stretch',
          borderTop: '1px dashed var(--border)',
          fontSize: 11,
        }}>
          {/* Etiket */}
          <div style={{ ...cellStyle, background: 'var(--surface)', minWidth: 90, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 9, color: mute, letterSpacing: '0.8px', fontWeight: 700 }}>DEFANS</div>
              <div style={{ fontSize: 10, color: 'var(--amber)', fontWeight: 700, marginTop: 3 }}>4x PLAN</div>
            </div>
          </div>

          {/* D1 */}
          <div style={cellStyle}>
            <div style={labelStyle}>D1 Tetik (-%5)</div>
            <div style={{ fontSize: 12, fontFamily: mono, color: 'var(--amber)', fontWeight: 600 }}>
              ${fmt(d1Trigger, 4)}
            </div>
            <div style={{ fontSize: 9, color: mute, marginTop: 3 }}>
              D1 Tetik: {fmt(d1Trigger, 2)} USDT (girişten -%5)
            </div>
            <div style={{ fontSize: 9, color: mute, marginTop: 1 }}>DCA +%20 slot · Binance ent. güncellenir</div>
          </div>

          {/* D2 */}
          <div style={cellStyle}>
            <div style={labelStyle}>D2 Tetik (-%12)</div>
            <div style={{ fontSize: 12, fontFamily: mono, color: 'var(--red)', fontWeight: 600 }}>
              ${fmt(d2Trigger, 4)}
            </div>
            <div style={{ fontSize: 9, color: mute, marginTop: 2 }}>
              D2 Tetik: {fmt(d2Trigger, 2)} USDT (girişten -%12)
            </div>
            <div style={{ fontSize: 11, fontFamily: mono, color: 'var(--green)', fontWeight: 700, marginTop: 3 }}>
              BE Hedefi: ${fmt(beTarget, 4)}
            </div>
            <div style={{ fontSize: 9, color: mute, marginTop: 1 }}>D1+D2 ağ.ort. × 1.0035</div>
          </div>

          {/* D3 */}
          <div style={{ ...cellStyle, borderRight: 'none', flex: 1 }}>
            <div style={labelStyle}>D3 (-%25)</div>
            <div style={{ fontSize: 11, color: 'var(--purple)', fontWeight: 700 }}>Hayalet SFP</div>
            <div style={{ fontSize: 9, color: mute, marginTop: 2 }}>
              Ana destek bölgesinde 5m Bull Bar onayı bekleniyor
            </div>
            <div style={{ fontSize: 9, color: 'var(--red)', marginTop: 4, fontWeight: 600 }}>
              Hard Stop: D3 iğnesi altına dinamik konur
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
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
                <React.Fragment key={p.posKey || i}>
                  <tr
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
                        background: isLong ? '#0ECB8118' : '#F6465D18',
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
                    <td style={{ color: '#F6465Daa', fontFamily: 'var(--mono)', fontSize: 11 }}>
                      ${fmt(p.liqPrice)}
                    </td>
                  </tr>
                  <TPRow pos={p} />
                  <DefenseRow pos={p} />
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
