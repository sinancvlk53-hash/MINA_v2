import React, { useEffect, useState } from 'react'

const DEFAULTS = {
  merterTimeStopH: 4,
  halukTimeStopH: 8,
  breakevenMult: 1.0020,
  dailyLossLimitPct: 20,
  telegramNotify: true,
  motorActive: true,
}

export default function SettingsPanel({ data, sendMessage, status }) {
  const server = data?.settings ?? {}
  const slotSummary = data?.slotSummary ?? {}

  const [form, setForm] = useState({ ...DEFAULTS, ...server })

  useEffect(() => {
    setForm((prev) => ({ ...DEFAULTS, ...prev, ...server }))
  }, [server.merterTimeStopH, server.halukTimeStopH, server.breakevenMult, server.dailyLossLimitPct, server.telegramNotify, server.motorActive])

  function patch(partial) {
    const next = { ...form, ...partial }
    setForm(next)
    sendMessage?.({ action: 'update_settings', settings: next })
  }

  const ei = slotSummary.merterEiMax ?? 2
  const merterOther = slotSummary.merterOtherMax ?? 1
  const haluk = slotSummary.motorMax ?? 7

  return (
    <div className="panel panel-settings">
      <div className="panel-head">
        <span className="panel-title">Ayarlar</span>
      </div>
      <div className="panel-body settings-body">
        <section className="settings-section">
          <h3 className="settings-section-title">Zaman stopu</h3>
          <label className="field-label">Merter DCA (saat)</label>
          <input
            className="field-input"
            type="number"
            min="1"
            max="168"
            step="1"
            value={form.merterTimeStopH}
            onChange={(e) => patch({ merterTimeStopH: Number(e.target.value) || 4 })}
          />
          <label className="field-label">Haluk motor (saat)</label>
          <input
            className="field-input"
            type="number"
            min="1"
            max="168"
            step="1"
            value={form.halukTimeStopH}
            onChange={(e) => patch({ halukTimeStopH: Number(e.target.value) || 8 })}
          />
        </section>

        <section className="settings-section">
          <h3 className="settings-section-title">Slot dağılımı</h3>
          <ul className="settings-slot-list">
            <li><span>EI tarama</span><strong>{ei} slot</strong></li>
            <li><span>Merter diğer (RSI)</span><strong>{merterOther} slot</strong></li>
            <li><span>Haluk 4x motor</span><strong>{haluk} slot</strong></li>
            <li className="settings-slot-total"><span>Toplam</span><strong>{slotSummary.slotTotal ?? 10} slot</strong></li>
          </ul>
        </section>

        <section className="settings-section">
          <h3 className="settings-section-title">Risk limiti</h3>
          <label className="field-label">Günlük zarar limiti (%)</label>
          <input
            className="field-input"
            type="number"
            min="5"
            max="50"
            step="1"
            value={form.dailyLossLimitPct}
            onChange={(e) => patch({ dailyLossLimitPct: Number(e.target.value) || 20 })}
          />
          <div className="field-hint">
            Vadeli bakiyenin yüzdesi — örn. %20 ve 5000 USDT → -1000 USDT limit
          </div>
        </section>

        <section className="settings-section">
          <h3 className="settings-section-title">Breakeven çarpanı</h3>
          <input
            className="field-input"
            type="number"
            min="1"
            max="1.05"
            step="0.0001"
            value={form.breakevenMult}
            onChange={(e) => patch({ breakevenMult: parseFloat(e.target.value) || 1.002 })}
          />
          <div className="field-hint">Merter BE çıkış: ortalama × çarpan</div>
        </section>

        <section className="settings-section settings-toggles">
          <label className="settings-toggle-row">
            <span>Telegram bildirimleri</span>
            <input
              type="checkbox"
              checked={!!form.telegramNotify}
              onChange={(e) => patch({ telegramNotify: e.target.checked })}
            />
          </label>
          <label className="settings-toggle-row">
            <span>Motor aktif</span>
            <input
              type="checkbox"
              checked={!!form.motorActive}
              onChange={(e) => patch({ motorActive: e.target.checked })}
            />
          </label>
        </section>

        <div className="field-hint" style={{ marginTop: 8 }}>
          {status === 'connected' ? 'Ayarlar sunucuya kaydedildi' : 'Bağlantı bekleniyor…'}
        </div>
      </div>
    </div>
  )
}
