import React from 'react'

const TABS = [
  { id: 'positions', label: 'Pozisyonlar', icon: '▦' },
  { id: 'defense',   label: 'Savunma',     icon: '🛡' },
  { id: 'chart',     label: 'Grafik',      icon: '📈' },
  { id: 'log',       label: 'Log',         icon: '📋' },
  { id: 'settings',  label: 'Ayarlar',     icon: '⚙' },
]

export default function MobileNav({ active, onChange, onLogOpen }) {
  function handleTabClick(id) {
    if (id === 'log') {
      onLogOpen?.()
      return
    }
    onChange(id)
  }

  return (
    <nav className="mobile-nav">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`mobile-nav-btn ${active === t.id ? 'active' : ''}`}
          onClick={() => handleTabClick(t.id)}
        >
          <span className="mobile-nav-icon">{t.icon}</span>
          <span className="mobile-nav-label">{t.label}</span>
        </button>
      ))}
    </nav>
  )
}
