import React, { useRef, useEffect, useState } from 'react'

function classify(line) {
  if (!line) return 'mute'
  const u = line.toUpperCase()
  if (u.includes('HAYALET') || u.includes('GHOST')) return 'mute'
  if (u.includes('ERROR') || u.includes('KRİTİK') || u.includes('HATA')) return 'error'
  if (u.includes('WARNING') || u.includes('UYARI')) return 'warn'
  if (u.includes('TP') || u.includes('STOP') || u.includes('SAVUNMA') || u.includes('DEFENSE')) return 'action'
  return 'info'
}

function filterGhostLines(lines) {
  return (lines || []).filter((line) => {
    const u = (line || '').toUpperCase()
    return !u.includes('HAYALET') && !u.includes('GHOST') && !line.includes('👻')
  })
}

export default function LogStream({ logs = [], testLogs = [], compact = false, fullscreen = false }) {
  const [liveMode, setLiveMode] = useState(true)
  const [testMode, setTestMode] = useState(false)
  const [seenCount, setSeenCount] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const endRef = useRef(null)
  const prevLen = useRef(0)

  const sourceLogs = filterGhostLines(testMode ? testLogs : logs)
  const [newFrom, setNewFrom] = useState(0)

  useEffect(() => {
    if (sourceLogs.length > prevLen.current) {
      setNewFrom(prevLen.current)
      setSeenCount(sourceLogs.length)
    }
    prevLen.current = sourceLogs.length
  }, [sourceLogs.length])

  useEffect(() => {
    if (liveMode && (expanded || !compact)) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [sourceLogs, liveMode, expanded, compact])

  const previewCount = compact && !expanded ? 3 : (compact ? 8 : 40)
  const displayLogs = fullscreen || expanded
    ? sourceLogs
    : sourceLogs.slice(-previewCount)

  function toggleExpand() {
    if (!compact) return
    setExpanded((v) => !v)
  }

  const body = (
    <>
      <div className="panel-head">
        <span className="panel-title">Log Akışı</span>
        <span className="panel-badge mono">{sourceLogs.length}</span>
        {compact && (
          <span className="field-hint log-tap-hint">{expanded ? 'Kapat' : 'Genişlet'}</span>
        )}
        <div className="log-toolbar">
          {!compact && (
            <>
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
            </>
          )}
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
    </>
  )

  if (expanded) {
    return (
      <div className="log-expand-overlay" onClick={() => setExpanded(false)} role="presentation">
        <div
          className="log-expand-panel panel panel-logs"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-label="Log tam ekran"
        >
          {body}
        </div>
      </div>
    )
  }

  return (
    <div
      className={`panel panel-logs ${compact ? 'compact log-compact-tap' : ''} ${fullscreen ? 'fullscreen' : ''}`}
      onClick={compact ? toggleExpand : undefined}
      onKeyDown={compact ? (e) => e.key === 'Enter' && toggleExpand() : undefined}
      role={compact ? 'button' : undefined}
      tabIndex={compact ? 0 : undefined}
      aria-label={compact ? 'Log akışını genişlet' : undefined}
    >
      {body}
    </div>
  )
}
