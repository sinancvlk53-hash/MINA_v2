import React, { useEffect, useState, useCallback, useMemo } from 'react'

function formatTs(ts) {
  if (!ts) return '—'
  return ts.replace('T', ' ').slice(0, 16)
}

function parseListingDate(row) {
  const raw = row.listedAt || row.firstMention
  if (!raw) return null
  const s = String(raw).trim()
  const normalized = s.includes('T') ? s : s.replace(' ', 'T')
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function ageHours(row) {
  const d = parseListingDate(row)
  if (!d) return Infinity
  return (Date.now() - d.getTime()) / 3600000
}

function hoursAgoLabel(h) {
  if (!Number.isFinite(h)) return '—'
  if (h < 1) return `${Math.max(1, Math.round(h * 60))}dk`
  if (h < 24) return `${Math.round(h)}sa`
  return `${Math.round(h / 24)}g`
}

function prepareListings(coins) {
  return (coins || [])
    .map((row) => ({ ...row, _ageH: ageHours(row) }))
    .filter((row) => row._ageH <= 48)
    .sort((a, b) => {
      const staleA = a._ageH > 24 ? 1 : 0
      const staleB = b._ageH > 24 ? 1 : 0
      if (staleA !== staleB) return staleA - staleB
      return a._ageH - b._ageH
    })
}

function ListingRow({ row }) {
  const ageH = row._ageH
  const cls = ageH > 24 ? 'listing-row listing-stale' : 'listing-row listing-fresh'
  const when = formatTs(row.listedAt || row.firstMention)

  return (
    <li className={cls}>
      <span className="listing-coin">{row.coin}</span>
      <span className="listing-time">{when}</span>
      <span className="listing-ago">{hoursAgoLabel(ageH)}</span>
    </li>
  )
}

function ListingSection({ title, coins, loading }) {
  const rows = useMemo(() => prepareListings(coins), [coins])

  return (
    <section className="radar-section">
      <div className="radar-section-head">
        <span className="radar-section-title">{title}</span>
        <span className="radar-count">{rows.length}</span>
      </div>
      {loading && <div className="radar-loading">…</div>}
      {!loading && rows.length === 0 && (
        <div className="radar-empty">—</div>
      )}
      {rows.length > 0 && (
        <ul className="listing-list">
          {rows.map((row) => (
            <ListingRow key={`${title}-${row.coin}-${row.listedAt || row.firstMention}`} row={row} />
          ))}
        </ul>
      )}
    </section>
  )
}

export default function HalukArchivePanel({ status, sendMessage, actionMsg }) {
  const [upbitCoins, setUpbitCoins] = useState([])
  const [upbitLoading, setUpbitLoading] = useState(false)
  const [binanceCoins, setBinanceCoins] = useState([])
  const [binanceLoading, setBinanceLoading] = useState(false)

  const fetchUpbit = useCallback(() => {
    if (status !== 'connected' || !sendMessage) return
    setUpbitLoading(true)
    sendMessage({ action: 'get_upbit_listings', limit: 300 })
  }, [status, sendMessage])

  const fetchBinance = useCallback(() => {
    if (status !== 'connected' || !sendMessage) return
    setBinanceLoading(true)
    sendMessage({ action: 'get_binance_new_listings' })
  }, [status, sendMessage])

  useEffect(() => {
    fetchUpbit()
  }, [fetchUpbit])

  useEffect(() => {
    fetchBinance()
  }, [fetchBinance])

  useEffect(() => {
    if (actionMsg?.action !== 'upbit_listings') return
    setUpbitLoading(false)
    setUpbitCoins(actionMsg.coins || [])
  }, [actionMsg])

  useEffect(() => {
    if (actionMsg?.action !== 'binance_new_listings') return
    setBinanceLoading(false)
    setBinanceCoins(actionMsg.coins || [])
  }, [actionMsg])

  return (
    <div className="panel macro-col-panel macro-radar">
      <ListingSection
        title="Upbit Yeni Listelemeleri"
        coins={upbitCoins}
        loading={upbitLoading}
      />
      <ListingSection
        title="Binance Yeni Listelemeleri"
        coins={binanceCoins}
        loading={binanceLoading}
      />
    </div>
  )
}
