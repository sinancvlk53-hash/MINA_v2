import React, { useEffect, useRef, useState } from 'react'
import PluginSlot from './PluginSlot.jsx'

export default function ChartLayer({ symbol }) {
  const containerRef = useRef(null)
  const [loaded, setLoaded]   = useState(false)
  const [current, setCurrent] = useState(null)

  useEffect(() => {
    if (!symbol || !containerRef.current) return
    if (symbol === current) return

    setCurrent(symbol)
    setLoaded(false)
    containerRef.current.innerHTML = ''

    const wrapper = document.createElement('div')
    wrapper.className = 'tradingview-widget-container'
    wrapper.style.height = '100%'
    wrapper.style.width  = '100%'

    const inner = document.createElement('div')
    inner.className = 'tradingview-widget-container__widget'
    inner.style.height = 'calc(100% - 32px)'
    inner.style.width  = '100%'
    wrapper.appendChild(inner)

    const script = document.createElement('script')
    script.type  = 'text/javascript'
    script.src   = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.async = true
    script.onload = () => setLoaded(true)
    script.textContent = JSON.stringify({
      autosize:            true,
      symbol:              'BINANCE:' + symbol,
      interval:            '15',
      timezone:            'Europe/Istanbul',
      theme:               'dark',
      style:               '1',
      locale:              'tr',
      backgroundColor:     '#0f1824',
      gridColor:           '#1c2a3a',
      hide_top_toolbar:    false,
      hide_legend:         false,
      allow_symbol_change: true,
      save_image:          false,
      support_host:        'https://www.tradingview.com',
    })
    wrapper.appendChild(script)
    containerRef.current.appendChild(wrapper)
  }, [symbol, current])

  if (!symbol) {
    return (
      <div className="section-card">
        <div className="section-header">
          <span className="section-title">Grafik</span>
          <span style={{ marginLeft: 'auto', color: 'var(--text-mute)', fontSize: 9 }}>TradingView</span>
        </div>
        <div style={{
          height: 360, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 6,
          color: 'var(--text-mute)', fontSize: 12
        }}>
          <span style={{ fontSize: 24, opacity: .3 }}>◈</span>
          Pozisyon satırına tıkla
        </div>
        <PluginSlot id="candle-analysis" label="Mum formasyonu modülü — yakında" />
      </div>
    )
  }

  if (!symbol.endsWith('USDT')) {
    return (
      <div className="section-card">
        <div className="section-header">
          <span className="section-title">Grafik — {symbol}</span>
        </div>
        <div style={{
          height: 360, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 6,
          color: 'var(--text-mute)', fontSize: 12
        }}>
          <span style={{ fontSize: 24, opacity: .3 }}>⊘</span>
          USDT dışı çiftler desteklenmiyor
        </div>
      </div>
    )
  }

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Grafik — {symbol}</span>
        <span style={{
          marginLeft: 'auto', padding: '1px 6px',
          background: '#3b82f618', color: 'var(--accent)',
          borderRadius: 3, fontSize: 9, fontWeight: 700
        }}>TRADINGVIEW</span>
      </div>
      <div ref={containerRef} className="chart-container" />
      <PluginSlot id="candle-analysis" label="Mum formasyonu modülü — yakında" />
    </div>
  )
}
