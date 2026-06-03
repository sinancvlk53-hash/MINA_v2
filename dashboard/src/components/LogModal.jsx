import React from 'react'
import LogStream from './LogStream.jsx'

export default function LogModal({ logs, testLogs, onClose }) {
  return (
    <div className="log-modal-overlay" onClick={onClose}>
      <div className="log-modal" onClick={(e) => e.stopPropagation()}>
        <div className="log-modal-header">
          <span className="log-modal-title">Log Akışı</span>
          <button type="button" className="log-modal-close" onClick={onClose} aria-label="Kapat">
            ✕
          </button>
        </div>
        <div className="log-modal-body">
          <LogStream logs={logs} testLogs={testLogs} fullscreen />
        </div>
      </div>
    </div>
  )
}
