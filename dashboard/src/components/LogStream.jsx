import React, { useRef, useEffect, useState } from 'react'

function classify(line) {
  if (!line) return 'mute'
  const u = line.toUpperCase()
  if (u.includes('ERROR') || u.includes('KRİTİK') || u.includes('HATA')) return 'error'
  if (u.includes('WARNING') || u.includes('UYARI') || u.includes('IP BAN')) return 'warn'
  if (u.includes('SAVUNMA') || u.includes('TP') || u.includes('STOP') || u.includes('KÂR') || u.includes('BAŞABAŞ')) return 'action'
  if (u.includes('BAŞLATILDI') || u.includes('ENGINE')) return 'boot'
  return 'info'
}

const COLORS = {
  error:  '#ef4444',
  warn:   '#f59e0b',
  action: '#3b82f6',
  boot:   '#10b981',
  info:   '#4a637d',
  mute:   '#2d3f50',
}

export default function LogStream({ logs }) {
  const [paused, setPaused] = useState(false)
  const endRef   = useRef(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (!paused) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, paused])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30
    setPaused(!atBottom)
  }

  return (
    <div className="section-card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 180 }}>
      <div className="section-header">
        <span className="section-title">Log Akışı</span>
        {paused && (
          <span style={{
            marginLeft: 6, padding: '1px 6px', borderRadius: 3,
            background: '#f59e0b18', color: 'var(--amber)', fontSize: 8, fontWeight: 700
          }}>DURDURULDU</span>
        )}
        <span style={{ marginLeft: 'auto', color: 'var(--text-mute)', fontSize: 9, fontFamily: 'var(--mono)' }}>
          {logs?.length ?? 0}
        </span>
      </div>

      <div
        ref={scrollRef}
        className="log-stream"
        onScroll={handleScroll}
        style={{ flex: 1 }}
      >
        {!logs || logs.length === 0 ? (
          <span style={{ color: '#2d4a63' }}>WebSocket bağlantısı bekleniyor...</span>
        ) : (
          logs.map((line, i) => (
            <div key={i} style={{ color: COLORS[classify(line)] }}>{line}</div>
          ))
        )}
        <div ref={endRef} />
      </div>

      {paused && (
        <button onClick={() => {
          setPaused(false)
          endRef.current?.scrollIntoView({ behavior: 'smooth' })
        }} style={{
          margin: '0 10px 8px',
          padding: '4px 10px', borderRadius: 5,
          background: 'var(--accent)', color: '#fff',
          border: 'none', fontSize: 10, fontWeight: 700, cursor: 'pointer'
        }}>↓ Sona git</button>
      )}
    </div>
  )
}
