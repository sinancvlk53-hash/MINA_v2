import React, { useEffect, useState, useCallback } from 'react'

const FILTERS = [
  { id: 'all', label: 'Tümü' },
  { id: 'sinyal', label: 'Sinyal' },
  { id: 'kutu', label: 'Kutu' },
  { id: 'makro', label: 'Makro' },
]

const TYPE_CLS = {
  sinyal: 'arch-type-sinyal',
  kutu: 'arch-type-kutu',
  makro: 'arch-type-makro',
  haber: 'arch-type-haber',
  diger: 'arch-type-diger',
}

function formatTs(ts) {
  if (!ts) return '—'
  return ts.replace('T', ' ').slice(0, 16)
}

function cardTitle(row) {
  if (row.coins_mentioned?.length) {
    return row.coins_mentioned.join(' · ')
  }
  return row.message_type || 'Mesaj'
}

function formatPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function formatPrice(v) {
  if (v == null || Number.isNaN(Number(v))) return null
  const n = Number(v)
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (n >= 1) return n.toFixed(4)
  return n.toFixed(6)
}

export default function HalukArchivePanel({ status, sendMessage, actionMsg }) {
  const [messageType, setMessageType] = useState('all')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [expanded, setExpanded] = useState(null)
  const [loading, setLoading] = useState(false)
  const [upbitCoins, setUpbitCoins] = useState([])
  const [upbitItems, setUpbitItems] = useState([])
  const [upbitLoading, setUpbitLoading] = useState(false)
  const [binanceCoins, setBinanceCoins] = useState([])
  const [binanceUpdatedAt, setBinanceUpdatedAt] = useState(null)
  const [binanceLoading, setBinanceLoading] = useState(false)
  const [traderPending, setTraderPending] = useState([])
  const [traderActive, setTraderActive] = useState([])
  const [traderTrades, setTraderTrades] = useState([])
  const [traderSummary, setTraderSummary] = useState(null)
  const [traderUpdatedAt, setTraderUpdatedAt] = useState(null)
  const [traderLoading, setTraderLoading] = useState(false)

  const fetchArchive = useCallback(() => {
    if (status !== 'connected' || !sendMessage) return
    setLoading(true)
    sendMessage({
      action: 'get_haluk_archive',
      messageType: messageType === 'all' ? undefined : messageType,
      limit: 80,
      offset: 0,
    })
  }, [status, sendMessage, messageType])

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

  const fetchUpbitTrader = useCallback(() => {
    if (status !== 'connected' || !sendMessage) return
    setTraderLoading(true)
    sendMessage({ action: 'get_upbit_trader_status' })
  }, [status, sendMessage])

  useEffect(() => {
    fetchArchive()
  }, [fetchArchive])

  useEffect(() => {
    fetchUpbit()
  }, [fetchUpbit])

  useEffect(() => {
    fetchBinance()
  }, [fetchBinance])

  useEffect(() => {
    fetchUpbitTrader()
    const t = setInterval(fetchUpbitTrader, 30000)
    return () => clearInterval(t)
  }, [fetchUpbitTrader])

  useEffect(() => {
    if (actionMsg?.action !== 'haluk_archive') return
    setLoading(false)
    setItems(actionMsg.items || [])
    setTotal(actionMsg.total ?? 0)
  }, [actionMsg])

  useEffect(() => {
    if (actionMsg?.action !== 'upbit_listings') return
    setUpbitLoading(false)
    setUpbitItems(actionMsg.items || [])
    setUpbitCoins(actionMsg.coins || [])
  }, [actionMsg])

  useEffect(() => {
    if (actionMsg?.action !== 'binance_new_listings') return
    setBinanceLoading(false)
    setBinanceCoins(actionMsg.coins || [])
    setBinanceUpdatedAt(actionMsg.updatedAt || null)
  }, [actionMsg])

  useEffect(() => {
    if (actionMsg?.action !== 'upbit_trader_status') return
    setTraderLoading(false)
    setTraderPending(actionMsg.pending || [])
    setTraderActive(actionMsg.active || [])
    setTraderTrades(actionMsg.recent_trades || [])
    setTraderSummary(actionMsg.summary || null)
    setTraderUpdatedAt(actionMsg.updated_at || null)
  }, [actionMsg])

  return (
    <div className="panel panel-archive">
      <div className="panel-head">
        <span className="panel-title">Haber</span>
        <span className="panel-badge">{total}</span>
      </div>

      <div className="panel-body archive-body">
        <section className="upbit-listings-section">
          <div className="upbit-listings-head">
            <h3 className="settings-section-title">Upbit Listelemeleri</h3>
            <span className="panel-badge">{upbitCoins.length}</span>
          </div>
          {upbitLoading && <p className="archive-loading">Upbit taraması…</p>}
          {!upbitLoading && upbitCoins.length === 0 && (
            <p className="field-hint">upbit / listing / listeleme içeren mesaj bulunamadı</p>
          )}
          {upbitCoins.length > 0 && (
            <>
              <div className="upbit-coin-grid-head">
                <span>Coin</span>
                <span>İlk bahis</span>
                <span>Bahis</span>
                <span>Fiyat Δ</span>
              </div>
              <ul className="upbit-coin-list">
                {upbitCoins.map((row) => {
                  const pct = row.priceChangePct
                  const pctPositive = pct != null && pct >= 0
                  return (
                    <li key={row.coin} className="upbit-coin-row">
                      <strong className="upbit-coin-symbol">{row.coin}</strong>
                      <span className="upbit-coin-date">{formatTs(row.firstMention || row.listedAt)}</span>
                      <span className="upbit-coin-count">{row.mentionCount ?? 1}×</span>
                      <span
                        className={`upbit-coin-pct ${pct == null ? '' : pctPositive ? 'text-green' : 'text-red'}`}
                        title={
                          row.priceThen != null && row.priceNow != null
                            ? `${formatPrice(row.priceThen)} → ${formatPrice(row.priceNow)}`
                            : 'Binance futures verisi yok'
                        }
                      >
                        {formatPct(pct)}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
          {upbitItems.length > 0 && (
            <details className="upbit-messages-details">
              <summary className="archive-expand-btn">{upbitItems.length} mesaj detayı</summary>
              <div className="upbit-message-list">
                {upbitItems.slice(0, 20).map((row) => (
                  <div key={row.id} className="upbit-message-item">
                    <span className="archive-ts">{formatTs(row.timestamp)}</span>
                    {row.coins?.length > 0 && (
                      <span className="archive-coins inline">
                        {row.coins.map((c) => (
                          <span key={c} className="arch-coin-tag">{c}</span>
                        ))}
                      </span>
                    )}
                    <p className="archive-summary">{row.summary || row.snippet}</p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>

        <section className="upbit-listings-section upbit-trader-section">
          <div className="upbit-listings-head">
            <h3 className="settings-section-title">Upbit Trader</h3>
            <span className="panel-badge">
              {(traderSummary?.watch_count ?? 0) + (traderSummary?.active_count ?? 0)}
            </span>
          </div>
          {traderUpdatedAt && (
            <p className="field-hint binance-updated-hint">Son güncelleme: {traderUpdatedAt}</p>
          )}
          {traderLoading && traderPending.length === 0 && traderActive.length === 0 && (
            <p className="archive-loading">Trader durumu…</p>
          )}

          {traderSummary && (
            <div className="upbit-trader-summary">
              <div className="upbit-trader-stat">
                <span className="upbit-trader-stat-label">Toplam K/Z</span>
                <span className={`upbit-trader-stat-value ${traderSummary.total_pnl >= 0 ? 'text-green' : 'text-red'}`}>
                  {traderSummary.total_pnl >= 0 ? '+' : ''}{Number(traderSummary.total_pnl).toFixed(2)} USDT
                </span>
              </div>
              <div className="upbit-trader-stat">
                <span className="upbit-trader-stat-label">Kapanan</span>
                <span className="upbit-trader-stat-value">{traderSummary.closed_count ?? 0}</span>
              </div>
              <div className="upbit-trader-stat">
                <span className="upbit-trader-stat-label">Kazanç</span>
                <span className="upbit-trader-stat-value text-green">{traderSummary.win_count ?? 0}</span>
              </div>
              <div className="upbit-trader-stat">
                <span className="upbit-trader-stat-label">Zarar</span>
                <span className="upbit-trader-stat-value text-red">{traderSummary.loss_count ?? 0}</span>
              </div>
            </div>
          )}

          {traderPending.length > 0 && (
            <>
              <p className="upbit-trader-subhead">İzlenen coinler</p>
              <ul className="upbit-trader-watch-list">
                {traderPending.map((row) => (
                  <li key={row.coin} className="upbit-trader-watch-row">
                    <span className="badge-pill badge-watch">İZLENİYOR</span>
                    <strong className="upbit-coin-symbol">{row.coin}</strong>
                    <span className="upbit-trader-meta">
                      Listeleme: {formatPrice(row.listing_price) ?? '—'}
                    </span>
                    <span className="upbit-trader-meta">
                      Zirve: {formatPrice(row.peak) ?? '—'}
                      {row.peak_frozen ? ' ✓' : ''}
                    </span>
                    <span className="upbit-coin-date">{row.started_at_display || '—'}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {traderActive.length > 0 && (
            <>
              <p className="upbit-trader-subhead">Aktif SHORT</p>
              <ul className="upbit-trader-active-list">
                {traderActive.map((row) => (
                  <li key={row.coin} className="upbit-trader-active-row">
                    <span className="badge-pill badge-short">SHORT 8x</span>
                    <strong className="upbit-coin-symbol">{row.coin}</strong>
                    <span className="upbit-trader-meta">Giriş: {formatPrice(row.entry_price) ?? '—'}</span>
                    <span className="upbit-trader-meta">TP: {formatPrice(row.tp_price) ?? '—'}</span>
                    {row.trade_id != null && (
                      <span className="upbit-trader-meta">DERR #{row.trade_id}</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}

          {!traderLoading && traderPending.length === 0 && traderActive.length === 0 && (
            <p className="field-hint">Şu an izlenen coin veya aktif pozisyon yok</p>
          )}

          {traderTrades.length > 0 && (
            <>
              <p className="upbit-trader-subhead">Son 10 işlem (DERR)</p>
              <div className="upbit-trader-trade-grid-head">
                <span>Coin</span>
                <span>Durum</span>
                <span>Giriş</span>
                <span>Çıkış</span>
                <span>K/Z</span>
              </div>
              <ul className="upbit-coin-list">
                {traderTrades.map((row) => {
                  const pnl = row.pnl_usdt
                  const pnlPositive = pnl != null && Number(pnl) >= 0
                  const isOpen = row.status === 'open'
                  return (
                    <li key={row.id} className="upbit-trader-trade-row">
                      <strong className="upbit-coin-symbol">{row.coin}</strong>
                      <span className={`badge-pill ${isOpen ? 'badge-watch' : 'arch-type-diger'}`}>
                        {isOpen ? 'Açık' : (row.close_reason || 'Kapalı')}
                      </span>
                      <span className="binance-price">{formatPrice(row.open_price) ?? '—'}</span>
                      <span className="binance-price">{isOpen ? '—' : (formatPrice(row.close_price) ?? '—')}</span>
                      <span className={`upbit-coin-pct ${pnl == null ? '' : pnlPositive ? 'text-green' : 'text-red'}`}>
                        {pnl == null ? '—' : `${pnlPositive ? '+' : ''}${Number(pnl).toFixed(2)}`}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </section>

        <section className="upbit-listings-section binance-listings-section">
          <div className="upbit-listings-head">
            <h3 className="settings-section-title">Binance Yeni Listelemeler</h3>
            <span className="panel-badge">{binanceCoins.length}</span>
          </div>
          {binanceUpdatedAt && (
            <p className="field-hint binance-updated-hint">Son güncelleme: {formatTs(binanceUpdatedAt)} · 6 saatte bir yenilenir</p>
          )}
          {binanceLoading && <p className="archive-loading">Binance taraması…</p>}
          {!binanceLoading && binanceCoins.length === 0 && (
            <p className="field-hint">Son 50 günde yeni perpetual listeleme bulunamadı</p>
          )}
          {binanceCoins.length > 0 && (
            <>
              <div className="binance-coin-grid-head">
                <span>Coin</span>
                <span>Listeleme</span>
                <span>İlk</span>
                <span>Güncel</span>
                <span>Δ</span>
              </div>
              <ul className="upbit-coin-list">
                {binanceCoins.map((row) => {
                  const pct = row.priceChangePct
                  const pctPositive = pct != null && pct >= 0
                  return (
                    <li key={row.symbol || row.coin} className="binance-coin-row">
                      <strong className="upbit-coin-symbol">{row.coin}</strong>
                      <span className="upbit-coin-date">{formatTs(row.listedAt)}</span>
                      <span className="binance-price">{formatPrice(row.priceThen) ?? '—'}</span>
                      <span className="binance-price">{formatPrice(row.priceNow) ?? '—'}</span>
                      <span className={`upbit-coin-pct ${pct == null ? '' : pctPositive ? 'text-green' : 'text-red'}`}>
                        {formatPct(pct)}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </section>

        <div className="archive-type-filters" role="tablist" aria-label="Mesaj tipi filtresi">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={messageType === f.id}
              className={`archive-filter-btn ${messageType === f.id ? 'active' : ''}`}
              onClick={() => setMessageType(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading && <p className="archive-loading">Yükleniyor…</p>}

        <div className="archive-list">
          {!loading && items.length === 0 && (
            <p className="empty-state sm">Kayıt bulunamadı</p>
          )}
          {items.map((row) => (
            <article key={row.id} className="archive-item">
              <div className="archive-item-head">
                <span className="archive-ts">{formatTs(row.timestamp)}</span>
                <span className={`badge-pill arch-type ${TYPE_CLS[row.message_type] || 'arch-type-diger'}`}>
                  {row.message_type}
                </span>
                {row.direction && row.direction !== 'None' && (
                  <span className={`badge-pill ${row.direction === 'AL' ? 'badge-long' : 'badge-short'}`}>
                    {row.direction}
                  </span>
                )}
              </div>

              <h3 className="archive-item-title">{cardTitle(row)}</h3>

              {(row.coins_mentioned?.length > 0) && (
                <div className="archive-coins">
                  {row.coins_mentioned.map((c) => (
                    <span key={c} className="arch-coin-tag">{c}</span>
                  ))}
                </div>
              )}

              {row.analysis_summary && (
                <p className="archive-summary">{row.analysis_summary}</p>
              )}

              {row.price_levels?.length > 0 && (
                <div className="archive-levels">
                  Seviye: {row.price_levels.join(' · ')}
                </div>
              )}

              <button
                type="button"
                className="archive-expand-btn"
                onClick={() => setExpanded(expanded === row.id ? null : row.id)}
              >
                {expanded === row.id ? 'Gizle' : 'Tam metin'}
              </button>
              {expanded === row.id && (
                <pre className="archive-raw">{row.raw_text}</pre>
              )}
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
