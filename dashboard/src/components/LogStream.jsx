import React, { useRef, useEffect, useState } from 'react'

function classify(line) {
  if (!line) return 'mute'
  const u = line.toUpperCase()
  if (u.includes('ERROR') || u.includes('KRİTİK') || u.includes('HATA')) return 'error'
  if (u.includes('WARNING') || u.includes('UYARI')) return 'warn'
  if (u.includes('TP') || u.includes('STOP') || u.includes('SAVUNMA') || u.includes('DEFENSE')) return 'action'
  return 'info'
}

export default function LogStream({ logs = [], testLogs = [], compact = false, fullscreen = false }) {
  const [liveMode, setLiveMode] = useState(true)
  const [testMode, setTestMode] = useState(false)
  const [seenCount, setSeenCount] = useState(0)
  const endRef = useRef(null)
  const prevLen = useRef(0)

  const sourceLogs = testMode ? testLogs : logs
  const [newFrom, setNewFrom] = useState(0)

  useEffect(() => {
    if (sourceLogs.length > prevLen.current) {
      setNewFrom(prevLen.current)
      setSeenCount(sourceLogs.length)
    }
    prevLen.current = sourceLogs.length
  }, [sourceLogs.length])

  useEffect(() => {
    if (liveMode) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [sourceLogs, liveMode])

  const displayLogs = fullscreen ? sourceLogs : (compact ? sourceLogs.slice(-8) : sourceLogs.slice(-40))

  return (
    <div className={`panel panel-logs ${compact ? 'compact' : ''} ${fullscreen ? 'fullscreen' : ''}`}>
      <div className="panel-head">
        <span className="panel-title">Log Akışı</span>
        <span className="panel-badge mono">{sourceLogs.length}</span>
        <div className="log-toolbar">
          <button
            type="button"
            className={`log-tool-btn ${liveMode ? 'active' : ''}`}
            onClick={() => setLiveMode(true)}
          >
            Canlı
          </button>
          <button
            type="button"
            className={`log-tool-btn ${testMode ? 'active' : ''}`}
            onClick={() => setTestMode((t) => !t)}
          >
            Test
          </button>
        </div>
      </div>
      <div className="log-stream">
        {displayLogs.length === 0 ? (
          <div className="log-line mute">WebSocket bağlantısı bekleniyor...</div>
        ) : (
          displayLogs.map((line, i) => {
            const globalIdx = sourceLogs.length - displayLogs.length + i
            const isNew = globalIdx >= newFrom && globalIdx >= seenCount - 5
            const kind = testMode ? 'test' : classify(line)
            return (
              <div
                key={`${globalIdx}-${line.slice(0, 24)}`}
                className={`log-line log-${kind} ${isNew ? 'log-slide-in' : ''}`}
              >
                {line}
              </div>
            )
          })
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
