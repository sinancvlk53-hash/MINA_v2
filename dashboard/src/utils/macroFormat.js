const TR_MONTHS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']

/** PDF dosya adı veya ISO timestamp → "9 Haz 2026 17:02" */
export function formatPdfTimestamp(input) {
  if (input == null || input === '') return null
  const s = String(input).trim()

  const tg = s.match(/tg_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/)
  if (tg) {
    const [, y, mo, d, h, mi] = tg
    return `${Number(d)} ${TR_MONTHS[Number(mo) - 1]} ${y} ${h}:${mi}`
  }

  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (iso) {
    const [, y, mo, d, h, mi] = iso
    return `${Number(d)} ${TR_MONTHS[Number(mo) - 1]} ${y} ${h}:${mi}`
  }

  const bare = s.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})/)
  if (bare) {
    const [, y, mo, d, h, mi] = bare
    return `${Number(d)} ${TR_MONTHS[Number(mo) - 1]} ${y} ${h}:${mi}`
  }

  return null
}

/** HALUK_PDF:dosya.pdf veya ham kaynak → tarih/saat */
export function formatMacroSource(source) {
  if (!source) return null
  const raw = String(source)
  const pdfPart = raw.includes(':') ? raw.split(':').slice(1).join(':') : raw
  const formatted = formatPdfTimestamp(pdfPart) || formatPdfTimestamp(raw)
  if (formatted) return formatted
  return raw
    .replace(/^HALUK_/i, '')
    .replace(/^haluk_/i, '')
    .replace(/\.pdf$/i, '')
}

export function formatMacroSnippet(text) {
  if (!text) return ''
  return String(text)
    .replace(/Muhtemelen çizilen/gi, "Hoca'nın Beklentisi")
    .replace(/Muhtemelen cizilen/gi, "Hoca'nın Beklentisi")
}

export function formatMacroDirection(dir) {
  if (dir === 'UP') return { text: '↑ Yukarı', cls: 'macro-dir-up' }
  if (dir === 'DOWN') return { text: '↓ Aşağı', cls: 'macro-dir-down' }
  if (dir === 'LIKELY' || dir === 'EXPECTED') {
    return { text: "Hoca'nın Beklentisi", cls: 'macro-dir-expected' }
  }
  return null
}
