import React, { useState, useEffect } from 'react'
import Header from './components/Header.jsx'
import OrderPanel from './components/OrderPanel.jsx'
import PositionTable from './components/PositionTable.jsx'
import PositionChartEmbed from './components/PositionChartEmbed.jsx'
import PositionDetailModal from './components/PositionDetailModal.jsx'
import DefensePanel from './components/DefensePanel.jsx'
import LogStream from './components/LogStream.jsx'
import LogModal from './components/LogModal.jsx'
import MobileNav from './components/MobileNav.jsx'
import useWebSocket from './hooks/useWebSocket.js'
import useMediaQuery from './hooks/useMediaQuery.js'
import './App.css'

const WS_URL = 'ws://178.105.150.40:8765'

export default function App() {
  const { data, status, sendMessage } = useWebSocket(WS_URL)
  const [detailPos, setDetailPos] = useState(null)
  const [mobileTab, setMobileTab] = useState('positions')
  const [logOpen, setLogOpen] = useState(false)
  const [selectedPos, setSelectedPos] = useState(null)
  const isMobile = useMediaQuery('(max-width: 768px)')

  const positions = data?.positions ?? []
  const logs = data?.logs ?? []
  const slotSize = (data?.balance ?? 0) / 10
  const chartPos = selectedPos ?? positions[0] ?? null

  useEffect(() => {
    if (positions.length && !selectedPos) {
      setSelectedPos(positions[0])
    }
  }, [positions, selectedPos])

  function handlePanic() {
    sendMessage({ action: 'close_all' })
  }

  const showLeft = mobileTab === 'settings'
  const showCenter = mobileTab === 'positions' || mobileTab === 'chart'
  const showRight = mobileTab === 'defense'
  return (
    <div className="app">
      <Header data={data} status={status} onPanic={handlePanic} />

      <main className="main-grid">
        <aside className={`col-left ${showLeft ? 'mobile-show' : 'mobile-hide'}`}>
          <OrderPanel data={data} status={status} />
        </aside>

        <section className={`col-center ${showCenter ? 'mobile-show' : 'mobile-hide'}`}>
          {(!isMobile || mobileTab === 'positions') && (
            <PositionTable
              positions={positions}
              onDetail={setDetailPos}
              sendMessage={sendMessage}
              slotSize={slotSize}
              onSelectPos={setSelectedPos}
            />
          )}

          {isMobile && mobileTab === 'chart' && (
            chartPos ? (
              <PositionChartEmbed pos={chartPos} slotSize={slotSize} mobile />
            ) : (
              <div className="panel">
                <div className="empty-state">Grafik için önce bir pozisyon seçin</div>
              </div>
            )
          )}

          {!isMobile && (
            <LogStream logs={logs} testLogs={data?.testLogs ?? []} />
          )}
        </section>

        <aside className={`col-right ${showRight ? 'mobile-show' : 'mobile-hide'}`}>
          <DefensePanel data={data} />
        </aside>
      </main>

      {isMobile && (
        <MobileNav
          active={mobileTab}
          onChange={setMobileTab}
          onLogOpen={() => setLogOpen(true)}
        />
      )}

      {logOpen && (
        <LogModal
          logs={logs}
          testLogs={data?.testLogs ?? []}
          onClose={() => setLogOpen(false)}
        />
      )}

      {detailPos && (
        <PositionDetailModal
          pos={detailPos}
          data={data}
          onClose={() => setDetailPos(null)}
        />
      )}
    </div>
  )
}
