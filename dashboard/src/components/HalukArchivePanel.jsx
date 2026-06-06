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

export default function HalukArchivePanel({ status, sendMessage, actionMsg }) {
  const [messageType, setMessageType] = useState('all')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [expanded, setExpanded] = useState(null)
  const [loading, setLoading] = useState(false)
  const [upbitCoins, setUpbitCoins] = useState([])
  const [upbitItems, setUpbitItems] = useState([])
  const [upbitLoading, setUpbitLoading] = useState(false)

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

  useEffect(() => {
    fetchArchive()
  }, [fetchArchive])

  useEffect(() => {
    fetchUpbit()
  }, [fetchUpbit])

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

  return (
    <div className="panel panel-archive">
      <div className="panel-head">
        <span className="panel-title">Haber</span>
        <span className="panel-badge">{total}</span>
      </div>

      <div className="panel-body archive-body">
        <section className="upbit-listings-section">
          <div className="upbit-listings-head">
            <h3 className="settings-section-title">Upbit Listeleme</h3>
            <span className="panel-badge">{upbitCoins.length}</span>
          </div>
          {upbitLoading && <p className="archive-loading">Upbit taraması…</p>}
          {!upbitLoading && upbitCoins.length === 0 && (
            <p className="field-hint">upbit / listing / listeleme içeren mesaj bulunamadı</p>
          )}
          {upbitCoins.length > 0 && (
            <ul className="upbit-coin-list">
              {upbitCoins.map((row) => (
                <li key={row.coin} className="upbit-coin-row">
                  <strong>{row.coin}</strong>
                  <span className="upbit-coin-date">{formatTs(row.listedAt)}</span>
                </li>
              ))}
            </ul>
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
