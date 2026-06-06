import React, { useState, useEffect } from 'react'
import Header from './components/Header.jsx'
import OrderPanel from './components/OrderPanel.jsx'
import PositionTable from './components/PositionTable.jsx'
import PositionDetailModal from './components/PositionDetailModal.jsx'
import DefensePanel from './components/DefensePanel.jsx'
import MacroLevelsPanel from './components/MacroLevelsPanel.jsx'
import SettingsPanel from './components/SettingsPanel.jsx'
import HalukArchivePanel from './components/HalukArchivePanel.jsx'
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
  const [mobileTab, setMobileTab] = useState('positions')
  const [selectedPos, setSelectedPos] = useState(null)
  const isMobile = useMediaQuery('(max-width: 768px)')

  const positions = (data?.positions ?? []).filter((p) => Number(p.amount) > 0)
  const motorPositions = (data?.motorPositions ?? positions.filter((p) => p.slotType !== 'merter'))
    .filter((p) => Number(p.amount) > 0)
  const merterPositions = (data?.merterPositions ?? positions.filter((p) => p.slotType === 'merter'))
    .filter((p) => Number(p.amount) > 0)
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
  const showArchive = !isMobile || mobileTab === 'archive'

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
      <Header data={data} status={status} onPanic={handlePanic} onLogout={logout} />

      <main className="main-grid">
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

        <section className={`col-center ${showPositions ? 'mobile-show' : 'mobile-hide'}`}>
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
          />
          <MacroLevelsPanel
            levels={macroLevels}
            coinsFilter={['TOTAL', 'OTHERS', 'BTC.D']}
            compact
          />
        </section>

        <aside className={`col-right ${showDefense || showSettings || showArchive ? 'mobile-show' : 'mobile-hide'}`}>
          {!isMobile && <MacroLevelsPanel levels={macroLevels} />}
          {showDefense && (
            <DefensePanel data={data} />
          )}
          {(showArchive || !isMobile) && (
            <HalukArchivePanel
              status={status}
              sendMessage={sendMessage}
              actionMsg={actionMsg}
            />
          )}
          {showSettings && (
            <SettingsPanel
              data={data}
              sendMessage={sendMessage}
              status={status}
              actionMsg={actionMsg}
              logs={logs}
              testLogs={data?.testLogs ?? []}
            />
          )}
        </aside>
      </main>

      {isMobile && (
        <MobileNav
          active={mobileTab}
          onChange={setMobileTab}
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
