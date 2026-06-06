import { useState, useEffect, useRef, useCallback } from 'react'

const TOKEN_KEY = 'mina_dashboard_token'
const TOKEN_EXP_KEY = 'mina_dashboard_token_exp'

function saveSession(token, expiresAt) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(TOKEN_EXP_KEY, String(expiresAt))
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(TOKEN_EXP_KEY)
}

function storedToken() {
  const token = localStorage.getItem(TOKEN_KEY)
  const exp = Number(localStorage.getItem(TOKEN_EXP_KEY) || 0)
  if (!token || !exp || exp <= Date.now()) {
    clearSession()
    return null
  }
  return token
}

export default function useWebSocket(url) {
  const [data, setData] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [authenticated, setAuthenticated] = useState(false)
  const [authRequired, setAuthRequired] = useState(true)
  const [loginError, setLoginError] = useState(null)
  const [actionMsg, setActionMsg] = useState(null)
  const [futuresSymbols, setFuturesSymbols] = useState([])
  const [markPrices, setMarkPrices] = useState({})
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        setStatus('connected')
        clearTimeout(reconnectRef.current)
        const token = storedToken()
        if (token) {
          ws.send(JSON.stringify({ action: 'auth', token }))
        }
      }

      ws.onmessage = (e) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(e.data)
          if (msg.action === 'auth_required') {
            setAuthRequired(true)
            setAuthenticated(false)
            return
          }
          if (msg.action === 'login_ok' || msg.action === 'auth_ok') {
            if (msg.token && msg.expiresAt) {
              saveSession(msg.token, msg.expiresAt)
            }
            setAuthenticated(true)
            setAuthRequired(false)
            setLoginError(null)
            return
          }
          if (msg.action === 'login_failed' || msg.action === 'auth_failed') {
            clearSession()
            setAuthenticated(false)
            setAuthRequired(true)
            setLoginError(msg.error || 'Giriş başarısız')
            setData(null)
            return
          }
          if (msg.action === 'logged_out') {
            clearSession()
            setAuthenticated(false)
            setAuthRequired(true)
            setData(null)
            return
          }
          if (msg.action === 'futures_symbols') {
            setFuturesSymbols(Array.isArray(msg.symbols) ? msg.symbols : [])
            return
          }
          if (msg.action === 'mark_price' && msg.symbol) {
            if (msg.price != null) {
              setMarkPrices((prev) => ({ ...prev, [msg.symbol]: msg.price }))
            }
            return
          }
          if (msg.action === 'settings_saved') {
            setData((prev) => (prev ? { ...prev, settings: msg.settings } : prev))
            setActionMsg(msg)
            return
          }
          if (msg.action) {
            setActionMsg(msg)
            return
          }
          if (msg.macroLevels != null || msg.positions != null || msg.balance != null) {
            setData(msg)
          }
        } catch {}
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setStatus('disconnected')
        setAuthenticated(false)
        reconnectRef.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        setStatus('error')
        ws.close()
      }
    } catch {
      setStatus('error')
      reconnectRef.current = setTimeout(connect, 5000)
    }
  }, [url])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const login = useCallback((username, password) => {
    setLoginError(null)
    sendMessage({ action: 'login', username, password })
  }, [sendMessage])

  const logout = useCallback(() => {
    clearSession()
    setAuthenticated(false)
    setAuthRequired(true)
    setData(null)
    setLoginError(null)
    sendMessage({ action: 'logout' })
  }, [sendMessage])

  const clearAction = useCallback(() => setActionMsg(null), [])

  return {
    data,
    status,
    sendMessage,
    actionMsg,
    clearAction,
    futuresSymbols,
    markPrices,
    authenticated,
    authRequired,
    loginError,
    login,
    logout,
  }
}
