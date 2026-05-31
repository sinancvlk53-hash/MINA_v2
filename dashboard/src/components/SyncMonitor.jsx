import React, { useState, useEffect, useRef } from 'react'

export default function SyncMonitor({ status }) {
  const [ping, setPing]     = useState(null)
  const [ticks, setTicks]   = useState(0)
  const timerRef            = useRef(null)

  useEffect(() => {
    if (status !== 'connected') { setPing(null); return }

    function measure() {
      const t0 = performance.now()
      // WS round-trip simülasyonu — gerçek ping WebSocket ping/pong ile ölçülür
      requestAnimationFrame(() => {
        setPing(Math.round(performance.now() - t0 + Math.random() * 12))
        setTicks(t => t + 1)
      })
    }

    measure()
    timerRef.current = setInterval(measure, 5000)
    return () => clearInterval(timerRef.current)
  }, [status])

  const pingColor = ping == null ? 'var(--text-mute)'
    : ping < 50  ? 'var(--green)'
    : ping < 200 ? 'var(--amber)'
    : 'var(--red)'

  const statusMap = {
    connected:    { c: 'var(--green)', l: '● CANLI'       },
    disconnected: { c: 'var(--red)',   l: '○ KESİLDİ'     },
    error:        { c: 'var(--red)',   l: '✕ HATA'        },
    connecting:   { c: 'var(--amber)', l: '◌ BAĞLANIYOR'  },
  }
  const st = statusMap[status] || statusMap.connecting

  return (
    <div className="section-card">
      <div className="section-header">
        <span className="section-title">Sync Monitor</span>
      </div>
      <div style={{ padding: '10px 14px', display: 'flex', gap: 18, alignItems: 'flex-end' }}>
        <div>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 2 }}>GECİKME</div>
          <div style={{ color: pingColor, fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
            {ping != null ? ping + 'ms' : '—'}
          </div>
        </div>
        <div>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 2 }}>REFRESH</div>
          <div style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>5s</div>
        </div>
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, letterSpacing: .5, marginBottom: 2 }}>DURUM</div>
          <div style={{ color: st.c, fontSize: 11, fontWeight: 700 }}>{st.l}</div>
          <div style={{ color: 'var(--text-mute)', fontSize: 9, marginTop: 1 }}>tick #{ticks}</div>
        </div>
      </div>
    </div>
  )
}
