import React, { useState, useMemo } from 'react'
import { POPULAR_SYMBOLS } from '../utils/trading.js'

const LEVERS = [1, 2, 3, 4, 5, 10]
const ORDER_TYPES = ['Market', 'Limit', 'Stop']

export default function OrderPanel({ data, status }) {
  const [query, setQuery]       = useState('')
  const [symbol, setSymbol]     = useState('BTCUSDT')
  const [side, setSide]         = useState('LONG')
  const [leverage, setLeverage] = useState(4)
  const [orderType, setOrderType] = useState('Market')
  const [amount, setAmount]     = useState('')
  const [showList, setShowList] = useState(false)

  const balance  = data?.balance ?? 0
  const slot     = balance / 10
  const entryMargin = slot / 5
  const posCount = data?.positionCount ?? 0

  const symbols = useMemo(() => {
    const fromPos = (data?.positions ?? []).map((p) => p.symbol)
    return [...new Set([...fromPos, ...POPULAR_SYMBOLS])].sort()
  }, [data?.positions])

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase()
    if (!q) return symbols.slice(0, 12)
    return symbols.filter((s) => s.includes(q)).slice(0, 12)
  }, [query, symbols])

  function pickSymbol(s) {
    setSymbol(s)
    setQuery(s.replace('USDT', ''))
    setShowList(false)
  }

  return (
    <div className="panel panel-order">
      <div className="panel-head">
        <span className="panel-title">Emir Paneli</span>
        <span className="panel-badge">{posCount}/10 slot</span>
      </div>

      <div className="panel-body">
        {/* Coin arama */}
        <label className="field-label">Coin</label>
        <div className="search-wrap">
          <input
            className="field-input"
            placeholder="BTC, ETH..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setShowList(true) }}
            onFocus={() => setShowList(true)}
            onBlur={() => setTimeout(() => setShowList(false), 150)}
          />
          {showList && filtered.length > 0 && (
            <ul className="search-dropdown">
              {filtered.map((s) => (
                <li key={s}>
                  <button type="button" onMouseDown={() => pickSymbol(s)}>{s}</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="field-hint">Seçili: <strong>{symbol}</strong></div>

        {/* Long / Short */}
        <label className="field-label">Yön</label>
        <div className="toggle-row">
          {['LONG', 'SHORT'].map((s) => (
            <button
              key={s}
              type="button"
              className={`toggle-btn ${side === s ? 'active' : ''} ${s === 'LONG' ? 'long' : 'short'}`}
              onClick={() => setSide(s)}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Kaldıraç */}
        <label className="field-label">Kaldıraç</label>
        <div className="leverage-grid">
          {LEVERS.map((l) => (
            <button
              key={l}
              type="button"
              className={`lev-btn ${leverage === l ? 'active' : ''}`}
              onClick={() => setLeverage(l)}
            >
              {l}x
            </button>
          ))}
        </div>

        {/* Emir tipi */}
        <label className="field-label">Emir Tipi</label>
        <div className="toggle-row three">
          {ORDER_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={`toggle-btn sm ${orderType === t ? 'active' : ''}`}
              onClick={() => setOrderType(t)}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Miktar */}
        <label className="field-label">Miktar (coin)</label>
        <input
          className="field-input"
          type="number"
          min="0"
          step="any"
          placeholder="0.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />

        <div className="slot-budget">
          <div className="slot-budget-row">
            <span>Slot bütçesi</span>
            <strong>{slot.toFixed(2)} USDT</strong>
          </div>
          <div className="slot-budget-row">
            <span>Giriş marjini (÷5)</span>
            <strong className="accent">{entryMargin.toFixed(2)} USDT</strong>
          </div>
          <div className="slot-budget-row">
            <span>Hacim ({leverage}x)</span>
            <strong>{(entryMargin * leverage).toFixed(2)} USDT</strong>
          </div>
        </div>

        {/* Slot görsel */}
        <div className="slot-bar">
          {Array.from({ length: 10 }, (_, i) => (
            <div key={i} className={`slot-cell ${i < posCount ? 'used' : ''}`} />
          ))}
        </div>

        {/* Sistem kuralları */}
        <div className="rules-box">
          <div className="rules-title">Sistem Kuralları</div>
          <ul className="rules-list">
            <li><span>10 Slot</span><span>Kasa ÷ 10</span></li>
            <li><span>Giriş</span><span>Slot ÷ 5 (%20)</span></li>
            <li><span>TP1</span><span>+%3 · %50 kapat</span></li>
            <li><span>TP2</span><span>+%5 · %50 kapat</span></li>
            <li><span>Trailing</span><span>%2 callback</span></li>
            {leverage === 4 && (
              <li><span>Defans</span><span>D1/D2/D3 aktif</span></li>
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
