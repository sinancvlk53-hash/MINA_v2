import React, { useEffect, useState } from 'react'
import { getManualOpenPreview } from '../utils/trading.js'

export default function ManualOpenConfirm({
  open,
  symbol,
  side,
  leverage,
  orderType,
  limitPrice,
  stopPrice,
  leverageStrategy = {},
  slotSize,
  status,
  actionMsg,
  onConfirm,
  onCancel,
  onClearAction,
}) {
  const [submitting, setSubmitting] = useState(false)
  const preview = getManualOpenPreview(leverage, slotSize, leverageStrategy)

  useEffect(() => {
    if (!open) {
      setSubmitting(false)
      onClearAction?.()
    }
  }, [open, onClearAction])

  useEffect(() => {
    if (!actionMsg || actionMsg.action !== 'manual_open_result') return
    setSubmitting(false)
  }, [actionMsg])

  if (!open) return null

  const limitInvalid = orderType === 'Limit' && !(parseFloat(limitPrice) > 0)
  const stopInvalid = orderType === 'Stop Market' && !(parseFloat(stopPrice) > 0)
  const result = actionMsg?.action === 'manual_open_result' ? actionMsg : null
  const done = !!result

  return (
    <div className="manual-open-overlay" role="dialog" aria-modal="true" aria-labelledby="manual-open-title">
      <div className="manual-open-modal">
        <h2 id="manual-open-title" className="manual-open-title">Pozisyon Onayı</h2>
        <p className="manual-open-sub">Emir gönderilmeden önce parametreleri kontrol edin.</p>

        <div className="manual-open-summary">
          <div className="manual-open-row">
            <span>Coin</span>
            <strong>{symbol}</strong>
          </div>
          <div className="manual-open-row">
            <span>Yön</span>
            <strong className={side === 'LONG' ? 'text-green' : 'text-red'}>{side}</strong>
          </div>
          <div className="manual-open-row">
            <span>Kaldıraç</span>
            <strong>{leverage}x</strong>
          </div>
          <div className="manual-open-row">
            <span>Hedef slot</span>
            <strong>{leverage === 1 ? 'Merter DCA (otomatik)' : 'Motor (otomatik)'}</strong>
          </div>
          <div className="manual-open-row">
            <span>Emir tipi</span>
            <strong>{orderType}</strong>
          </div>
          {orderType === 'Limit' && (
            <div className="manual-open-row">
              <span>Limit fiyat</span>
              <strong>{limitPrice || '—'}</strong>
            </div>
          )}
          {orderType === 'Stop Market' && (
            <div className="manual-open-row">
              <span>Tetik fiyat</span>
              <strong>{stopPrice || '—'}</strong>
            </div>
          )}
        </div>

        <div className="manual-open-rules">
          <div className="manual-open-rules-title">Otomatik hesaplanan kurallar</div>
          {preview.fullManual && (
            <div className="manual-open-warn">⚠️ Full Manuel — motor müdahale etmez</div>
          )}
          <ul>
            <li><span>Marjin</span><span>{preview.marginLabel} = {preview.margin.toFixed(2)} USDT</span></li>
            <li><span>Hacim</span><span>{preview.notional.toFixed(2)} USDT</span></li>
            <li><span>TP1</span><span>{preview.tp1} · %50 kapat</span></li>
            <li><span>TP2</span><span>{preview.tp2}</span></li>
            <li><span>Trailing</span><span>{preview.trailing}</span></li>
            {preview.hasDefense ? (
              <>
                <li><span>D1</span><span>{preview.defense.d1}</span></li>
                <li><span>D2</span><span>{preview.defense.d2}</span></li>
                <li><span>Hard Stop</span><span>{preview.defense.hardStop}</span></li>
              </>
            ) : preview.stopLoss ? (
              <li><span>Stop-loss</span><span>{preview.stopLoss}</span></li>
            ) : null}
          </ul>
        </div>

        {result && (
          <div className={`manual-open-result ${result.ok ? 'ok' : 'err'}`}>
            {result.ok ? '✓ Emir gönderildi' : '✗ Hata'}
            {result.output && (
              <pre>{result.output}</pre>
            )}
          </div>
        )}

        <div className="manual-open-actions">
          {done ? (
            <button
              type="button"
              className="btn btn-manual-confirm manual-open-btn-confirm manual-open-btn-ok"
              onClick={onCancel}
            >
              Tamam
            </button>
          ) : (
            <>
              <button
                type="button"
                className="btn btn-ghost manual-open-btn-cancel"
                onClick={onCancel}
                disabled={submitting}
              >
                İptal
              </button>
              <button
                type="button"
                className="btn btn-manual-confirm manual-open-btn-confirm"
                disabled={status !== 'connected' || submitting || limitInvalid || stopInvalid}
                onClick={() => {
                  setSubmitting(true)
                  onConfirm()
                }}
              >
                {submitting ? 'Gönderiliyor…' : 'Onayla ve Aç'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
