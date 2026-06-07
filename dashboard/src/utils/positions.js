/** Merter 1x DCA vs motor pozisyon ayrımı — WS + fallback heuristik. */
export function isMerterPosition(p) {
  if (!p) return false
  if (p.slotType === 'merter') return true
  if (p.leverage === 1 && p.side === 'LONG') {
    if (p.merterYuva) return true
    const src = String(p.signalSource || '').toUpperCase()
    if (src === 'MZ' || src.startsWith('MERTER')) return true
  }
  return false
}

export function splitPositions(motorPositions = [], merterPositions = [], legacyPositions = []) {
  const seen = new Set()
  const merged = [...motorPositions, ...merterPositions, ...(legacyPositions || [])].filter((p) => {
    if (Number(p.amount) <= 0) return false
    const k = p.posKey || `${p.symbol}_${p.side}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
  const motor = merged.filter((p) => !isMerterPosition(p))
  const merter = merged.filter((p) => isMerterPosition(p))
  return { motor, merter, all: [...motor, ...merter] }
}

/** State dolu ama Binance'te görünmeyen yuvalar */
export function merterGhostSlots(merterSlots = {}, merterPositions = []) {
  const openSyms = new Set(merterPositions.map((p) => p.symbol))
  return Object.entries(merterSlots || {})
    .filter(([, slot]) => slot?.occupied && slot?.symbol && !openSyms.has(slot.symbol))
    .map(([yuva, slot]) => ({ yuva, ...slot }))
}
