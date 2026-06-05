import React, { useMemo } from 'react'
import { fmt, calcDefense } from '../utils/trading.js'

function priceToTopPct(price, minP, maxP) {
  if (maxP <= minP) return 50
  return ((maxP - price) / (maxP - minP)) * 100
}

function DefenseLinesOverlay({ pos, slotSize }) {
  const def = calcDefense(pos, slotSize)
  if (!def || pos.leverage !== 4) return null

  const { entryPrice, markPrice, liqPrice } = pos
  const prices = [entryPrice, markPrice, def.d1Price, def.d2Price, def.d3Price, liqPrice].filter(
    (v) => v != null && !isNaN(v) && v > 0
  )
  const minP = Math.min(...prices) * 0.992
  const maxP = Math.max(...prices) * 1.008

  const levels = [
    { key: 'D1', price: def.d1Price, cls: 'chart-line-d1', color: '#f0b90b' },
    { key: 'D2', price: def.d2Price, cls: 'chart-line-d2', color: '#ff9800' },
    { key: 'D3', price: def.d3Price, cls: 'chart-line-d3', color: '#f6465d' },
  ]

  return (
    <div className="chart-lines-overlay" aria-hidden="true">
      {levels.map(({ key, price, cls, color }) => (
        <div
          key={key}
          className={`chart-hline ${cls}`}
          style={{ top: `${priceToTopPct(price, minP, maxP)}%` }}
        >
          <span className="chart-hline-label" style={{ borderColor: color, color }}>
            {key} {fmt(price, 4)}
          </span>
          <span className="chart-hline-bar" style={{ background: color }} />
        </div>
      ))}
    </div>
  )
}

export default function PositionChartEmbed({ pos, slotSize = 0, mobile = false }) {
  const symbol = pos?.symbol

  const iframeSrc = useMemo(() => {
    if (!symbol) return ''
    const params = new URLSearchParams({
      symbol: `BINANCE:${symbol}`,
      theme: 'dark',
      style: '1',
      locale: 'tr',
      toolbar_bg: '#131722',
      enable_publishing: 'false',
      hide_top_toolbar: 'false',
      save_image: 'false',
      container_id: 'tv_chart',
    })
    return `https://www.tradingview.com/widgetembed/?${params.toString()}`
  }, [symbol])

  if (!pos) return null

  return (
    <div className={`panel panel-chart ${mobile ? 'panel-chart-mobile' : ''}`}>
      <div className="panel-head">
        <span className="panel-title">Grafik — {symbol}</span>
        <span className={`badge ${pos.side === 'LONG' ? 'badge-long' : 'badge-short'}`}>{pos.side}</span>
        <span className="panel-badge mono">Mark ${fmt(pos.markPrice, 4)}</span>
      </div>
      <div className="chart-embed-wrap">
        <DefenseLinesOverlay pos={pos} slotSize={slotSize} />
        <iframe
          key={symbol}
          title={`${symbol} chart`}
          src={iframeSrc}
          width="100%"
          height="400"
          frameBorder="0"
          className="chart-iframe"
        />
      </div>
    </div>
  )
}
