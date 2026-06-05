import React, { useState, useEffect } from 'react'
import Header from './components/Header.jsx'
import OrderPanel from './components/OrderPanel.jsx'
import PositionTable from './components/PositionTable.jsx'
import PositionDetailModal from './components/PositionDetailModal.jsx'
import DefensePanel from './components/DefensePanel.jsx'
import MacroLevelsPanel from './components/MacroLevelsPanel.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
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
  const motorPositions = data?.motorPositions ?? positions.filter((p) => p.slotType !== 'merter')
  const merterPositions = data?.merterPositions ?? positions.filter((p) => p.slotType === 'merter')
  const merterSlots = data?.merterSlots ?? {}
  const macroLevels = data?.macroLevels ?? []
  const logs = data?.logs ?? []
  const slotSize = (data?.balance ?? 0) / 10

  useEffect(() => {
    if (positions.length && !selectedPos) {
      setSelectedPos(positions[0])
    }
  }, [positions, selectedPos])

  function handlePanic() {
    sendMessage({ action: 'close_all' })
  }

  const showOrder = !isMobile || mobileTab === 'order'
  const showPositions = !isMobile || mobileTab === 'positions'
  const showDefense = !isMobile || mobileTab === 'defense'
  const showSettings = !isMobile || mobileTab === 'settings'

  return (
    <div className="app">
      <Header data={data} status={status} onPanic={handlePanic} />

      <main className="main-grid">
        <aside className={`col-left ${showOrder ? 'mobile-show' : 'mobile-hide'}`}>
          <OrderPanel data={data} status={status} sendMessage={sendMessage} />
        </aside>

        <section className={`col-center ${showPositions ? 'mobile-show' : 'mobile-hide'}`}>
          {isMobile && (
            <MacroLevelsPanel levels={macroLevels} />
          )}
          <PositionTable
            motorPositions={motorPositions}
            merterPositions={merterPositions}
            merterSlots={merterSlots}
            positions={positions}
            onDetail={setDetailPos}
            sendMessage={sendMessage}
            slotSize={slotSize}
            onSelectPos={setSelectedPos}
            selectedPos={selectedPos}
            showInlineChart={!isMobile}
          />

          {!isMobile && (
            <LogStream logs={logs} testLogs={data?.testLogs ?? []} />
          )}
        </section>

        <aside className={`col-right ${showDefense || showSettings ? 'mobile-show' : 'mobile-hide'}`}>
          {showDefense && (
            <>
              {!isMobile && <MacroLevelsPanel levels={macroLevels} />}
              <DefensePanel data={data} />
            </>
          )}
          {showSettings && (
            <SettingsPanel data={data} sendMessage={sendMessage} status={status} />
          )}
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
