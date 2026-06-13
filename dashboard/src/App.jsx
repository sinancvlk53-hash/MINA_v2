import React, { useState, useEffect } from 'react'

import Header from './components/Header.jsx'
import OrderPanel from './components/OrderPanel.jsx'
import PositionTable from './components/PositionTable.jsx'
import PositionDetailModal from './components/PositionDetailModal.jsx'
import PositionsOverlay from './components/PositionsOverlay.jsx'
import DefensePanel from './components/DefensePanel.jsx'
import MacroLevelsPanel from './components/MacroLevelsPanel.jsx'
import MacroWatcherPanel from './components/MacroWatcherPanel.jsx'
import HalukArchivePanel from './components/HalukArchivePanel.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import LogPanel from './components/LogPanel.jsx'
import DesktopNav from './components/DesktopNav.jsx'
import MobileNav from './components/MobileNav.jsx'
import LoginScreen from './components/LoginScreen.jsx'
import useWebSocket from './hooks/useWebSocket.js'
import useMediaQuery from './hooks/useMediaQuery.js'

import './App.css'

const WS_URL = 'ws://178.105.150.40:8765'

export default function App() {
  const {
    data, status, sendMessage, actionMsg, clearAction, futuresSymbols, markPrices,
    authenticated, authRequired, loginError, login, logout,
  } = useWebSocket(WS_URL)
  const [detailPos, setDetailPos] = useState(null)
  const [activeTab, setActiveTab] = useState('order')
  const [positionsOpen, setPositionsOpen] = useState(false)
  const [selectedPos, setSelectedPos] = useState(null)
  const isMobile = useMediaQuery('(max-width: 768px)')

  const positions = (data?.positions ?? []).filter((p) => Number(p.amount) > 0)
  const motorPositions = (data?.motorPositions ?? positions.filter((p) => p.slotType !== 'merter'))
    .filter((p) => Number(p.amount) > 0)
  const merterPositions = (data?.merterPositions ?? positions.filter((p) => p.slotType === 'merter'))
    .filter((p) => Number(p.amount) > 0)
  const merterSlots = data?.merterSlots ?? {}
  const macroLevels = data?.macroLevels ?? []
  const macroWatcher = data?.macroWatcher ?? null
  const halukPdfTimestamp = data?.halukPdfTimestamp ?? null
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

  const showOrder = activeTab === 'order'
  const showMacro = activeTab === 'macro'
  const showDefense = activeTab === 'defense'
  const showSettings = activeTab === 'settings'

  if (authRequired || !authenticated) {
    return (
      <LoginScreen
        onLogin={login}
        error={loginError}
        status={status}
        connecting={status === 'connecting'}
      />
    )
  }

  return (
    <div className="app">
      <Header
        data={data}
        status={status}
        onPanic={handlePanic}
        onLogout={logout}
        onPositionsClick={() => setPositionsOpen(true)}
      />

      {!isMobile && (
        <DesktopNav active={activeTab} onChange={setActiveTab} />
      )}

      <main className={`main-grid tab-${activeTab}`}>
        <aside className={`col-left ${showOrder ? 'mobile-show' : 'mobile-hide'}`}>
          <OrderPanel
            data={data}
            status={status}
            sendMessage={sendMessage}
            actionMsg={actionMsg}
            onClearAction={clearAction}
            futuresSymbols={futuresSymbols}
            markPrices={markPrices}
          />
        </aside>

        <section className={`col-center ${showMacro ? 'mobile-show' : 'mobile-hide'}`}>
          {showMacro && (
            <div className="macro-grid-3col">
              <MacroWatcherPanel watcher={macroWatcher} />
              <MacroLevelsPanel
                levels={macroLevels}
                halukPdfTimestamp={halukPdfTimestamp}
              />
              <HalukArchivePanel
                status={status}
                sendMessage={sendMessage}
                actionMsg={actionMsg}
              />
            </div>
          )}
        </section>

        <aside className={`col-right ${showDefense || showSettings ? 'mobile-show' : 'mobile-hide'}`}>
          {showDefense && (
            <DefensePanel data={data} />
          )}
          {showSettings && (
            <>
              <SettingsPanel
                data={data}
                sendMessage={sendMessage}
                status={status}
                actionMsg={actionMsg}
              />
              <LogPanel logs={logs} testLogs={data?.testLogs ?? []} />
            </>
          )}
        </aside>
      </main>

      {isMobile && (
        <MobileNav
          active={activeTab}
          onChange={setActiveTab}
        />
      )}

      <PositionsOverlay open={positionsOpen} onClose={() => setPositionsOpen(false)}>
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
          leverageStrategy={data?.settings?.leverageStrategy ?? {}}
          onOpenPositions={() => setPositionsOpen(true)}
        />
      </PositionsOverlay>

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
