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

/** Favoriler eşleşen sonuçların başında; kalanlar alfabetik */
export function filterFuturesSymbolsWithFavorites(symbols, query, favoriteBases, limit = 20) {
  if (!symbols?.length) return []
  const favSet = new Set((favoriteBases || []).map((b) => b.toUpperCase().replace(/USDT$/, '')))
  const matched = filterFuturesSymbols(symbols, query, symbols.length)
  const favFirst = matched.filter((sym) => favSet.has(sym.replace(/USDT$/, '')))
  const rest = matched
    .filter((sym) => !favSet.has(sym.replace(/USDT$/, '')))
    .sort((a, b) => a.localeCompare(b))
  return [...favFirst, ...rest].slice(0, limit)
}

export function formatMarkPrice(price) {
  if (price == null || Number.isNaN(Number(price))) return '—'
  const n = Number(price)
  if (n >= 1000) return n.toFixed(2)
  if (n >= 1) return n.toFixed(4)
  if (n >= 0.01) return n.toFixed(4)
  return n.toFixed(6)
}
