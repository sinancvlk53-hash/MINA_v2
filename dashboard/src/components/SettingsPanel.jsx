import React, { useEffect, useState } from 'react'
import FollowersPanel from './FollowersPanel.jsx'

const DEFAULT_LEVERAGE_STRATEGY = {
  '1': 'defense',
  '2': 'defense',
  '3': 'defense',
  '5': 'defense',
  '10': 'defense',
}

const DEFAULTS = {
  merterTimeStopH: 4,
  halukTimeStopH: 8,
  breakevenMult: 1.0020,
  dailyLossLimitPct: 20,
  telegramNotify: true,
  motorActive: true,
  leverageStrategy: { ...DEFAULT_LEVERAGE_STRATEGY },
}

const STRATEGY_LEVERS = [1, 2, 3, 5, 10]

const STRATEGY_OPTIONS = [
  { value: 'defense', label: 'Savunma modu' },
  { value: 'stop', label: 'Stop modu' },
  { value: 'ht', label: 'HT Stratejisi' },
  { value: 'full_manual', label: 'Full Manuel' },
]

export default function SettingsPanel({ data, sendMessage, status, actionMsg }) {
  const server = data?.settings ?? {}
  const slotSummary = data?.slotSummary ?? {}

  const [form, setForm] = useState({ ...DEFAULTS, ...server, leverageStrategy: { ...DEFAULT_LEVERAGE_STRATEGY, ...(server.leverageStrategy || {}) } })
  const [dailyLossInput, setDailyLossInput] = useState(String(server.dailyLossLimitPct ?? DEFAULTS.dailyLossLimitPct))
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveNote, setSaveNote] = useState('')

  useEffect(() => {
    if (dirty) return
    setForm({
      ...DEFAULTS,
      ...server,
      leverageStrategy: { ...DEFAULT_LEVERAGE_STRATEGY, ...(server.leverageStrategy || {}) },
    })
    setDailyLossInput(String(server.dailyLossLimitPct ?? DEFAULTS.dailyLossLimitPct))
  }, [server, dirty])

  useEffect(() => {
    if (actionMsg?.action !== 'settings_saved') return
    setSaving(false)
    setDirty(false)
    setSaveNote('Ayarlar kaydedildi')
    setForm({
      ...DEFAULTS,
      ...actionMsg.settings,
      leverageStrategy: { ...DEFAULT_LEVERAGE_STRATEGY, ...(actionMsg.settings?.leverageStrategy || {}) },
    })
    setDailyLossInput(String(actionMsg.settings?.dailyLossLimitPct ?? DEFAULTS.dailyLossLimitPct))
  }, [actionMsg])

  useEffect(() => {
    if (actionMsg?.action === 'error' && saving) {
      setSaving(false)
      setSaveNote(actionMsg.message || 'Kayıt hatası')
    }
  }, [actionMsg, saving])

  function updateField(partial) {
    setForm((prev) => ({ ...prev, ...partial }))
    setDirty(true)
    setSaveNote('')
  }

  function updateLeverageStrategy(lev, mode) {
    setForm((prev) => ({
      ...prev,
      leverageStrategy: { ...prev.leverageStrategy, [String(lev)]: mode },
    }))
    setDirty(true)
    setSaveNote('')
  }

  function handleSave() {
    if (status !== 'connected' || !sendMessage) return
    const parsedDaily = parseFloat(String(dailyLossInput).replace(',', '.'))
    if (Number.isNaN(parsedDaily) || parsedDaily < 5 || parsedDaily > 50) {
      setSaveNote('Günlük zarar limiti 5–50 arası olmalı')
      return
    }
    setSaving(true)
    setSaveNote('')
    const payload = {
      merterTimeStopH: Number(form.merterTimeStopH) || DEFAULTS.merterTimeStopH,
      halukTimeStopH: Number(form.halukTimeStopH) || DEFAULTS.halukTimeStopH,
      dailyLossLimitPct: parsedDaily,
      breakevenMult: Number(form.breakevenMult) || DEFAULTS.breakevenMult,
      telegramNotify: !!form.telegramNotify,
      motorActive: !!form.motorActive,
      leverageStrategy: { ...form.leverageStrategy },
    }
    sendMessage({ action: 'update_settings', settings: payload })
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
            onChange={(e) => updateField({ merterTimeStopH: Number(e.target.value) || 4 })}
          />
          <label className="field-label">Haluk motor (saat)</label>
          <input
            className="field-input"
            type="number"
            min="1"
            max="168"
            step="1"
            value={form.halukTimeStopH}
            onChange={(e) => updateField({ halukTimeStopH: Number(e.target.value) || 8 })}
          />
        </section>

        <section className="settings-section">
          <h3 className="settings-section-title">Kaldıraç stratejisi</h3>
          <div className="field-hint settings-strategy-hint">
            Savunma: D1/D2/D3 · Stop: sabit % stop · HT: %2 stop, 1:2/1:4 R/R · Full Manuel: motor müdahale etmez
          </div>
          <div className="settings-strategy-row settings-strategy-locked">
            <span className="settings-strategy-lev">4x</span>
            <span className="settings-strategy-mode">Savunma modu (sabit)</span>
          </div>
          {STRATEGY_LEVERS.map((lev) => (
            <div key={lev} className="settings-strategy-row">
              <span className="settings-strategy-lev">{lev}x</span>
              <select
                className="field-input settings-strategy-select"
                value={form.leverageStrategy[String(lev)] || 'defense'}
                onChange={(e) => updateLeverageStrategy(lev, e.target.value)}
              >
                {STRATEGY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          ))}
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
            type="text"
            inputMode="decimal"
            placeholder="20"
            value={dailyLossInput}
            onChange={(e) => {
              setDailyLossInput(e.target.value)
              setDirty(true)
              setSaveNote('')
            }}
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
            onChange={(e) => updateField({ breakevenMult: parseFloat(e.target.value) || 1.002 })}
          />
          <div className="field-hint">Merter BE çıkış: ortalama × çarpan</div>
        </section>

        <section className="settings-section settings-toggles">
          <label className="settings-toggle-row">
            <span>Telegram bildirimleri</span>
            <input
              type="checkbox"
              checked={!!form.telegramNotify}
              onChange={(e) => updateField({ telegramNotify: e.target.checked })}
            />
          </label>
          <label className="settings-toggle-row">
            <span>Motor aktif</span>
            <input
              type="checkbox"
              checked={!!form.motorActive}
              onChange={(e) => updateField({ motorActive: e.target.checked })}
            />
          </label>
        </section>

        <section className="settings-section">
          <h3 className="settings-section-title">Takipçiler</h3>
          <FollowersPanel data={data} embedded />
        </section>

        <button
          type="button"
          className="btn btn-settings-save"
          disabled={status !== 'connected' || saving}
          onClick={handleSave}
        >
          {saving ? 'Kaydediliyor…' : 'Kaydet'}
        </button>

        <div className={`field-hint settings-save-note ${saveNote.includes('hata') ? 'err' : saveNote ? 'ok' : ''}`}>
          {saveNote || (status === 'connected' ? (dirty ? 'Kaydedilmemiş değişiklikler var' : 'Sunucu ile senkron') : 'Bağlantı bekleniyor…')}
        </div>
      </div>
    </div>
  )
}
