import { useState, useEffect, useRef, useCallback } from 'react'

export default function useWebSocket(url) {
  const [data, setData]     = useState(null)
  const [status, setStatus] = useState('connecting')
  const wsRef        = useRef(null)
  const reconnectRef = useRef(null)
  const mountedRef   = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        setStatus('connected')
        clearTimeout(reconnectRef.current)
      }

      ws.onmessage = (e) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(e.data)
          if (msg.action) return
          if (msg.macroLevels != null || msg.positions != null || msg.balance != null) {
            setData(msg)
          }
        } catch {}
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setStatus('disconnected')
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

  return { data, status, sendMessage }
}
