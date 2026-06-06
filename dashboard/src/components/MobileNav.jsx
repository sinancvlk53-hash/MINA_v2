import React from 'react'

const TABS = [
  { id: 'order', label: 'Al/Sat', icon: '⇄' },
  { id: 'positions', label: 'Pozisyon', icon: '▦' },
  { id: 'defense', label: 'Savunma', icon: '🛡' },
  { id: 'archive', label: 'Haber', icon: '📰' },
  { id: 'settings', label: 'Ayarlar', icon: '⚙' },
]

export default function MobileNav({ active, onChange }) {
  return (
    <nav className="mobile-nav">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`mobile-nav-btn ${active === t.id ? 'active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          <span className="mobile-nav-icon">{t.icon}</span>
          <span className="mobile-nav-label">{t.label}</span>
        </button>
      ))}
    </nav>
  )
}
