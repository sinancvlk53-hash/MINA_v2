/** Binance Futures USDT perpetual sembol filtreleme */
export function normalizeSymbolQuery(raw) {
  const q = (raw || '').trim().toUpperCase()
  if (!q) return ''
  return q.endsWith('USDT') ? q : q
}

export function filterFuturesSymbols(symbols, query, limit = 20) {
  if (!symbols?.length) return []
  const q = normalizeSymbolQuery(query)
  if (!q) return symbols.slice(0, limit)
  return symbols
    .filter((sym) => {
      const base = sym.replace(/USDT$/, '')
      return sym.includes(q) || base.startsWith(q) || sym.startsWith(q)
    })
    .slice(0, limit)
}

export function formatMarkPrice(price) {
  if (price == null || Number.isNaN(Number(price))) return '—'
  const n = Number(price)
  if (n >= 1000) return n.toFixed(2)
  if (n >= 1) return n.toFixed(4)
  if (n >= 0.01) return n.toFixed(4)
  return n.toFixed(6)
}
