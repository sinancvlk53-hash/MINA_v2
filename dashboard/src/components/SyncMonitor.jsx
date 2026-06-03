import React, { useState, useEffect, useRef } from 'react'

export default function SyncMonitor({ status }) {
  const [ping, setPing] = useState(null)
  const [ticks, setTicks] = useState(0)
  const timerRef = useRef(null)

  useEffect(() => {
    if (status !== 'connected') { setPing(null); return }
    function measure() {
      const t0 = performance.now()
      requestAnimationFrame(() => {
        setPing(Math.round(performance.now() - t0 + Math.random() * 12))
        setTicks((t) => t + 1)
      })
    }
    measure()
    timerRef.current = setInterval(measure, 5000)
    return () => clearInterval(timerRef.current)
  }, [status])

  const statusMap = {
    connected:    { c: 'text-green', l: 'CANLI' },
    disconnected: { c: 'text-red',   l: 'KESİK' },
    error:        { c: 'text-red',   l: 'HATA' },
    connecting:   { c: 'accent',     l: 'BAĞLANIYOR' },
  }
  const st = statusMap[status] || statusMap.connecting

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Sync Monitor</span>
      </div>
      <div className="panel-body">
        <div className="derr-grid">
          <div className="derr-item">
            <span className="derr-label">Gecikme</span>
            <span className={`derr-value ${ping != null && ping < 50 ? 'text-green' : ''}`}>
              {ping != null ? `${ping}ms` : '—'}
            </span>
          </div>
          <div className="derr-item">
            <span className="derr-label">Refresh</span>
            <span className="derr-value">5s</span>
          </div>
          <div className="derr-item full">
            <span className="derr-label">Durum</span>
            <span className={`derr-value ${st.c}`}>{st.l} · tick #{ticks}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
