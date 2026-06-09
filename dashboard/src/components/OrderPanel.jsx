import React, { useState, useEffect, useRef } from 'react'
import { filterFuturesSymbolsWithFavorites, formatMarkPrice } from '../utils/symbols.js'
import { resolveStrategyMode, getManualOpenPreview } from '../utils/trading.js'
import {
  loadFavoriteCoins,
  saveFavoriteCoins,
  isFavoriteCoin,
  toggleFavoriteCoin,
  coinBase,
} from '../utils/favoriteCoins.js'
import ManualOpenConfirm from './ManualOpenConfirm.jsx'

const LEVERS = [1, 2, 3, 4, 5, 10]
const ENTRY_ORDER_TYPES = ['Market', 'Limit', 'Stop Market']

export default function OrderPanel({
  data,
  status,
  sendMessage,
  actionMsg,
  onClearAction,
  futuresSymbols = [],
  markPrices = {},
}) {
  const [query, setQuery] = useState('BTC')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [side, setSide] = useState('LONG')
  const [leverage, setLeverage] = useState(4)
  const [orderType, setOrderType] = useState('Market')
  const [limitPrice, setLimitPrice] = useState('')
  const [stopPrice, setStopPrice] = useState('')
  const [showList, setShowList] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [favorites, setFavorites] = useState(loadFavoriteCoins)
  const searchRef = useRef(null)

  const balance = data?.balance ?? 0
  const slot = balance / 10
  const leverageStrategy = data?.settings?.leverageStrategy ?? {}
  const strategyMode = resolveStrategyMode(leverage, leverageStrategy)
  const preview = getManualOpenPreview(leverage, slot, leverageStrategy)
  const entryMargin = preview.margin
  const slotSummary = data?.slotSummary ?? {}
  const motorUsed = slotSummary.motorUsed ?? data?.motorCount ?? 0
  const merterUsed = slotSummary.merterUsed ?? data?.merterCount ?? 0
  const motorMax = slotSummary.motorMax ?? 8
  const merterMax = slotSummary.merterMax ?? 3
  const slotTarget = leverage === 1 ? 'Merter DCA' : 'Motor'
  const merterLongOnly = leverage === 1 && side === 'SHORT'
  const posCount = data?.positionCount ?? 0

  const filtered = filterFuturesSymbolsWithFavorites(futuresSymbols, query, favorites, 20)
  const markPrice = markPrices[symbol]
  const currentBase = coinBase(query || symbol)
  const isFav = isFavoriteCoin(favorites, currentBase)

  useEffect(() => {
    if (leverage === 1) {
      if (side === 'SHORT') setSide('LONG')
      if (orderType !== 'Market') setOrderType('Market')
    }
  }, [leverage, side, orderType])

  useEffect(() => {
    if (status !== 'connected' || !sendMessage) return
    sendMessage({ action: 'get_futures_symbols' })
  }, [status, sendMessage])

  useEffect(() => {
    if (status !== 'connected' || !sendMessage || !symbol) return
    const fetchPrice = () => sendMessage({ action: 'get_mark_price', symbol })
    fetchPrice()
    const id = setInterval(fetchPrice, 5000)
    return () => clearInterval(id)
  }, [status, sendMessage, symbol])

  function pickSymbol(s) {
    setSymbol(s)
    setQuery(s.replace(/USDT$/, ''))
    setShowList(false)
  }

  function handleQueryChange(value) {
    setQuery(value)
    setShowList(true)
    const upper = value.trim().toUpperCase()
    if (upper.endsWith('USDT') && futuresSymbols.includes(upper)) {
      setSymbol(upper)
    }
  }

  function openConfirm() {
    if (status !== 'connected') return
    onClearAction?.()
    setConfirmOpen(true)
  }

  function orderTypePayload() {
    if (orderType === 'Stop Market') return 'stop_market'
    if (orderType === 'Limit') return 'limit'
    return 'market'
  }

  function handleConfirmOpen() {
    if (!sendMessage) return
    sendMessage({
      action: 'manual_open',
      symbol,
      side,
      leverage,
      orderType: orderTypePayload(),
      entryPrice: orderType === 'Limit' && limitPrice ? parseFloat(limitPrice) : undefined,
      stopPrice: orderType === 'Stop Market' && stopPrice ? parseFloat(stopPrice) : undefined,
    })
  }

  function closeConfirm() {
    setConfirmOpen(false)
    onClearAction?.()
  }

  function handleToggleFavorite() {
    if (!currentBase) return
    const next = toggleFavoriteCoin(favorites, currentBase)
    setFavorites(next)
    saveFavoriteCoins(next)
  }

  return (
    <>
      <div className="panel panel-order">
        <div className="panel-head">
          <span className="panel-title">Emir Paneli</span>
          <span className="panel-badge">{posCount}/10 slot</span>
        </div>

        <div className="panel-body">
          <div className="slot-status-line">
            Motor: <strong>{motorUsed}/{motorMax}</strong> dolu
            {' | '}
            Merter DCA: <strong>{merterUsed}/{merterMax}</strong> dolu
          </div>
          <div className="field-hint slot-auto-hint">
            {leverage === 1
              ? '1x → otomatik boş Merter DCA slotu (LONG)'
              : `${leverage}x → otomatik boş motor slotu`}
          </div>

          <label className="field-label">Coin</label>
          <div className="search-wrap search-wrap-with-fav">
            <input
              ref={searchRef}
              className="field-input search-input-with-fav"
              placeholder="SOL, BTC, ETH..."
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onFocus={() => setShowList(true)}
              onBlur={() => setTimeout(() => setShowList(false), 180)}
              autoComplete="off"
            />
            <button
              type="button"
              className={`fav-coin-btn ${isFav ? 'active' : ''}`}
              onClick={handleToggleFavorite}
              title={isFav ? 'Favorilerden çıkar' : 'Favorilere ekle'}
              aria-label={isFav ? 'Favorilerden çıkar' : 'Favorilere ekle'}
              aria-pressed={isFav}
            >
              ⭐
            </button>
            {showList && (
              <ul className="search-dropdown">
                {filtered.length > 0 ? (
                  filtered.map((s) => (
                    <li key={s}>
                      <button type="button" onMouseDown={() => pickSymbol(s)}>
                        {isFavoriteCoin(favorites, s) && (
                          <span className="search-fav-mark" aria-hidden>⭐</span>
                        )}
                        <span className="search-sym-base">{s.replace(/USDT$/, '')}</span>
                        <span className="search-sym-quote">USDT</span>
                      </button>
                    </li>
                  ))
                ) : (
                  <li className="search-empty">
                    {futuresSymbols.length ? 'Eşleşme yok' : 'Sembol listesi yükleniyor…'}
                  </li>
                )}
              </ul>
            )}
          </div>
          <div className="field-hint coin-selected-row">
            <span>Seçili: <strong>{symbol}</strong></span>
            {markPrice != null && (
              <span className="coin-live-price">
                Şu an: <strong>{formatMarkPrice(markPrice)}</strong> USDT
              </span>
            )}
          </div>

          <label className="field-label">Yön</label>
          <div className="toggle-row">
            {['LONG', 'SHORT'].map((s) => (
              <button
                key={s}
                type="button"
                className={`toggle-btn ${side === s ? 'active' : ''} ${s === 'LONG' ? 'long' : 'short'}`}
                onClick={() => setSide(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <label className="field-label">Kaldıraç</label>
          <div className="leverage-grid">
            {LEVERS.map((l) => (
              <button
                key={l}
                type="button"
                className={`lev-btn ${leverage === l ? 'active' : ''}`}
                onClick={() => setLeverage(l)}
              >
                {l}x
              </button>
            ))}
          </div>

          <label className="field-label">Emir tipi</label>
          {leverage === 1 ? (
            <div className="field-hint">Merter DCA: yalnızca Market</div>
          ) : (
          <div className="toggle-row three">
            {ENTRY_ORDER_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                className={`toggle-btn ${orderType === t ? 'active' : ''}`}
                onClick={() => setOrderType(t)}
              >
                {t}
              </button>
            ))}
          </div>
          )}

          {orderType === 'Limit' && (
            <>
              <label className="field-label">Limit fiyat (USDT)</label>
              <input
                className="field-input"
                type="number"
                min="0"
                step="any"
                placeholder={markPrice != null ? formatMarkPrice(markPrice) : 'Giriş seviyesi'}
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
              />
              <div className="field-hint">
                LONG: mark altında limit bekler · SHORT: mark üstünde limit bekler
              </div>
            </>
          )}

          {orderType === 'Stop Market' && (
            <>
              <label className="field-label">Tetik fiyatı (USDT)</label>
              <input
                className="field-input"
                type="number"
                min="0"
                step="any"
                placeholder={markPrice != null ? formatMarkPrice(markPrice) : 'Tetik seviyesi'}
                value={stopPrice}
                onChange={(e) => setStopPrice(e.target.value)}
              />
              <div className="field-hint">
                LONG: fiyat tetik üstüne çıkınca al · SHORT: fiyat tetik altına inince sat
              </div>
            </>
          )}

          <button
            type="button"
            className="btn btn-manual-open"
            disabled={status !== 'connected' || !symbol || merterLongOnly}
            onClick={openConfirm}
          >
            Manuel Aç
          </button>
          {merterLongOnly && (
            <div className="field-hint manual-open-footnote text-red">
              Merter DCA (1x) yalnızca LONG destekler
            </div>
          )}
          {strategyMode === 'full_manual' && leverage !== 1 && (
            <div className="field-hint manual-open-footnote text-amber">
              ⚠️ Full Manuel mod — motor müdahale etmez (TP/stop/savunma yok)
            </div>
          )}
          <div className="field-hint manual-open-footnote">
            Otomatik slot: {slotTarget} · Marjin {preview.marginLabel}
          </div>

          <div className="slot-budget">
            <div className="slot-budget-row">
              <span>Slot bütçesi</span>
              <strong>{slot.toFixed(2)} USDT</strong>
            </div>
            <div className="slot-budget-row">
              <span>Giriş marjini</span>
              <strong className="accent">{entryMargin.toFixed(2)} USDT</strong>
            </div>
            <div className="slot-budget-row">
              <span>Hacim ({leverage}x)</span>
              <strong>{(entryMargin * leverage).toFixed(2)} USDT</strong>
            </div>
          </div>

          <div className="rules-box">
            <div className="rules-title">Sistem Kuralları ({strategyMode})</div>
            <ul className="rules-list">
              <li><span>10 Slot</span><span>Kasa ÷ 10</span></li>
              <li><span>Giriş</span><span>{preview.marginLabel}</span></li>
              {strategyMode === 'ht' ? (
                <>
                  <li><span>Stop</span><span>-2% sabit</span></li>
                  <li><span>TP1</span><span>+4% · %50 · BE stop</span></li>
                  <li><span>TP2</span><span>+8% · kalan tamam</span></li>
                </>
              ) : strategyMode === 'ht_pdf' ? (
                <>
                  <li><span>Giriş / TP / Stop</span><span>Hoca seviyeleri</span></li>
                  <li><span>Emir</span><span>Limit kuyruk</span></li>
                </>
              ) : strategyMode === 'full_manual' ? (
                <li><span>Motor</span><span>⚠️ müdahale etmez</span></li>
              ) : (
                <>
                  <li><span>TP1</span><span>+%3 · %50 kapat</span></li>
                  <li><span>TP2</span><span>+%5 · %50 kapat</span></li>
                  <li><span>Trailing</span><span>%2 callback</span></li>
                  {leverage === 4 && (
                    <li><span>Defans</span><span>D1 -5% · D2 -12% · HS -25%</span></li>
                  )}
                </>
              )}
            </ul>
          </div>
        </div>
      </div>

      <ManualOpenConfirm
        open={confirmOpen}
        symbol={symbol}
        side={side}
        leverage={leverage}
        orderType={orderType}
        limitPrice={limitPrice}
        stopPrice={stopPrice}
        leverageStrategy={leverageStrategy}
        slotSize={slot}
        status={status}
        actionMsg={actionMsg}
        onConfirm={handleConfirmOpen}
        onCancel={closeConfirm}
        onClearAction={onClearAction}
      />
    </>
  )
}
