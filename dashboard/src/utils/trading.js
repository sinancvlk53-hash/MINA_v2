export function fmt(n, d = 4) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toFixed(d)
}

export function getLevRules(lev) {
  if (lev === 10) {
    return { tp_type: 'fast', tp1_pct: 2, tp2_pct: 4, tp2_close: 1.0, trailing_callback: null }
  }
  return { tp_type: 'standard', tp1_pct: 3, tp2_pct: 5, tp2_close: 0.5, trailing_callback: 2.0 }
}

export function calcTP(pos) {
  const { entryPrice, amount, leverage, side } = pos
  const rules = getLevRules(leverage)
  const { tp1_pct, tp2_pct, tp2_close, trailing_callback, tp_type } = rules
  const dir = side === 'LONG' ? 1 : -1

  const tp1Price = entryPrice * (1 + dir * tp1_pct / 100)
  const tp2Price = entryPrice * (1 + dir * tp2_pct / 100)
  const tp1Qty = amount * 0.5
  const tp2Qty = amount * 0.5 * tp2_close
  const tp1Usdt = (tp1Price - entryPrice) * tp1Qty * dir
  const tp2Usdt = (tp2Price - entryPrice) * tp2Qty * dir

  return { tp1Price, tp2Price, tp1Usdt, tp2Usdt, trailing_callback, tp_type, tp1_pct, tp2_pct, tp1Qty, tp2Qty }
}

export function calcDefense(pos, slotSize = 0) {
  const { entryPrice, side, leverage } = pos
  if (leverage !== 4) return null

  const isLong = side === 'LONG'
  const mul = (m) => (isLong ? entryPrice * m : entryPrice / m)

  const d1Price = mul(0.95)
  const d2Price = mul(0.88)
  const d3Price = mul(0.75)
  const hardStop = mul(0.75)
  const slot = slotSize || 0
  const d1Usdt = slot / 5
  const d2Usdt = slot / 5
  const d3Usdt = slot * 0.4

  return { d1Price, d2Price, d3Price, hardStop, d1Usdt, d2Usdt, d3Usdt, isLong }
}

export function defenseStageLabel(level) {
  if (level >= 3) return { text: 'D3', cls: 'stage-d3' }
  if (level >= 2) return { text: 'D2', cls: 'stage-d2' }
  if (level >= 1) return { text: 'D1', cls: 'stage-d1' }
  return { text: '—', cls: 'stage-none' }
}

export const POPULAR_SYMBOLS = [
  'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
  'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'ZECUSDT',
  'TAUSDT', 'BCHUSDT', 'USUSDT', 'LABUSDT',
]
