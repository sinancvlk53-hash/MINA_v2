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
  error:  '#F6465D',
  warn:   '#F0B90B',
  action: '#3b82f6',
  boot:   '#0ECB81',
  info:   '#5E6673',
  mute:   '#2d3f50',
}

export default function LogStream({ logs = [], testLogs = [] }) {
  const [expanded,   setExpanded]   = useState(false)
  const [liveMode,   setLiveMode]   = useState(true)
  const [testMode,   setTestMode]   = useState(false)
  const [frozenLogs, setFrozenLogs] = useState(null)
  const [blink,      setBlink]      = useState(true)
  const endRef = useRef(null)

  const sourceLogs    = testMode ? testLogs : logs
  const displayedLogs = (liveMode || frozenLogs === null) ? sourceLogs : frozenLogs

  // Blink yeşil yanıp sönme — canlı mod aktifken
  useEffect(() => {
    if (!liveMode) return
    const t = setInterval(() => setBlink(b => !b), 600)
    return () => clearInterval(t)
  }, [liveMode])

  // Canlı + açık modda otomatik alta kaydır
  useEffect(() => {
    if (liveMode && expanded) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [displayedLogs, liveMode, expanded])

  const toggleLive = () => {
    if (liveMode) {
      setFrozenLogs([...sourceLogs])
      setLiveMode(false)
    } else {
      setFrozenLogs(null)
      setLiveMode(true)
    }
  }

  const shownLogs   = expanded ? displayedLogs : displayedLogs.slice(-3)
  const hiddenCount = Math.max(0, displayedLogs.length - 3)

  const btnBase = {
    padding: '2px 8px', borderRadius: 3, fontSize: 9, fontWeight: 700,
    cursor: 'pointer',
  }

  return (
    <div className="section-card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="section-header">
        <span className="section-title">Log Akışı</span>
        <span style={{ marginLeft: 6, color: 'var(--text-mute)', fontSize: 9, fontFamily: 'var(--mono)' }}>
          {displayedLogs.length}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center' }}>
          {/* Canlı İzle */}
          <button onClick={toggleLive} style={{
            ...btnBase,
            background: liveMode ? (blink ? '#0ECB8135' : '#0ECB8115') : 'transparent',
            color: liveMode ? '#0ECB81' : 'var(--text-mute)',
            border: `1px solid ${liveMode ? '#0ECB8155' : 'var(--border)'}`,
            transition: 'background .3s',
          }}>🔴 Canlı İzle</button>

          {/* Test Akışı */}
          <button onClick={() => setTestMode(t => !t)} style={{
            ...btnBase,
            background: testMode ? '#F0B90B18' : 'transparent',
            color: testMode ? '#F0B90B' : 'var(--text-mute)',
            border: `1px solid ${testMode ? '#F0B90B55' : 'var(--border)'}`,
          }}>🧪 Test Akışını İzle</button>
        </div>
      </div>

      {/* Log satırları */}
      <div
        className="log-stream"
        style={{ maxHeight: expanded ? 220 : 'none', overflowY: expanded ? 'auto' : 'visible' }}
      >
        {displayedLogs.length === 0 ? (
          <span style={{ color: '#2d4a63' }}>
            {testMode ? 'Test logu yok...' : 'WebSocket bağlantısı bekleniyor...'}
          </span>
        ) : (
          shownLogs.map((line, i) => (
            <div key={i} style={{ color: testMode ? '#F0B90B' : COLORS[classify(line)] }}>
              {line}
            </div>
          ))
        )}
        {expanded && <div ref={endRef} />}
      </div>

      {/* Devamını Gör / Daralt */}
      {hiddenCount > 0 && (
        <button onClick={() => setExpanded(e => !e)} style={{
          margin: '0 10px 8px',
          padding: '5px 10px', borderRadius: 5,
          background: 'var(--card)', color: 'var(--text-mute)',
          border: '1px solid var(--border)', fontSize: 10, fontWeight: 700,
          cursor: 'pointer', width: 'calc(100% - 20px)', textAlign: 'center',
        }}>
          {expanded ? '▲ Daralt' : `Devamını Gör ▼  (+${hiddenCount} satır)`}
        </button>
      )}
    </div>
  )
}
