import React from 'react'
import { APP_TABS } from '../navTabs.js'

export default function MobileNav({ active, onChange }) {
  return (
    <nav className="mobile-nav" aria-label="Ana menü">
      {APP_TABS.map((t) => (
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
