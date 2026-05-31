import React, { useState } from 'react'
import Header          from './components/Header.jsx'
import AccountCard     from './components/AccountCard.jsx'
import CopyTradeConfig from './components/CopyTradeConfig.jsx'
import SyncMonitor     from './components/SyncMonitor.jsx'
import PanicButton     from './components/PanicButton.jsx'
import PositionTable   from './components/PositionTable.jsx'
import ChartLayer      from './components/ChartLayer.jsx'
import DefensePanel    from './components/DefensePanel.jsx'
import LogStream       from './components/LogStream.jsx'
import useWebSocket    from './hooks/useWebSocket.js'
import './App.css'

const WS_URL = 'ws://178.105.150.40:8765'

export default function App() {
  const { data, status, sendMessage } = useWebSocket(WS_URL)
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  const positions = data?.positions ?? []
  const logs      = data?.logs      ?? []

  function handlePanic() {
    sendMessage({ action: 'close_all' })
  }

  return (
    <div className="app">
      <Header data={data} status={status} />

      <div className="main-grid">

        {/* ── SOL SÜTUN ── hesap yönetimi */}
        <aside className="col-left">
          <AccountCard     data={data} />
          <CopyTradeConfig />
          <SyncMonitor     status={status} />
          <PanicButton     onPanic={handlePanic} disabled={status !== 'connected'} />
        </aside>

        {/* ── ORTA SÜTUN ── pozisyon tablosu + grafik */}
        <section className="col-center">
          <PositionTable
            positions={positions}
            selected={selectedSymbol}
            onSelect={setSelectedSymbol}
          />
          <ChartLayer symbol={selectedSymbol || positions[0]?.symbol || null} />
        </section>

        {/* ── SAĞ SÜTUN ── savunma + log */}
        <aside className="col-right">
          <DefensePanel data={data} />
          <LogStream    logs={logs} />
        </aside>

      </div>
    </div>
  )
}
