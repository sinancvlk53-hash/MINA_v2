import React from 'react'
import { APP_TABS } from '../navTabs.js'

export default function DesktopNav({ active, onChange }) {
  return (
    <nav className="desktop-nav" aria-label="Ana menü">
      {APP_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`desktop-nav-btn ${active === t.id ? 'active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          <span className="desktop-nav-icon">{t.icon}</span>
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  )
}
