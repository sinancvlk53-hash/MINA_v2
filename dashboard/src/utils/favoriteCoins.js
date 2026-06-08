const STORAGE_KEY = 'mina_favorite_coins'

export const DEFAULT_FAVORITE_COINS = ['BTC', 'ETH', 'SOL', 'BNB', 'AVAX', 'LINK', 'ARB', 'OP']

export function loadFavoriteCoins() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return [...DEFAULT_FAVORITE_COINS]
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed) || !parsed.length) return [...DEFAULT_FAVORITE_COINS]
    return parsed.map((s) => String(s).toUpperCase().replace(/USDT$/, ''))
  } catch {
    return [...DEFAULT_FAVORITE_COINS]
  }
}

export function saveFavoriteCoins(coins) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(coins))
}

export function coinBase(symbolOrBase) {
  return String(symbolOrBase || '').toUpperCase().replace(/USDT$/, '')
}

export function isFavoriteCoin(coins, symbolOrBase) {
  return coins.includes(coinBase(symbolOrBase))
}

export function toggleFavoriteCoin(coins, symbolOrBase) {
  const base = coinBase(symbolOrBase)
  if (!base) return coins
  const set = new Set(coins)
  if (set.has(base)) set.delete(base)
  else set.add(base)
  return [...set]
}
