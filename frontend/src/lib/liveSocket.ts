// One shared WebSocket for the whole app: robot position/status, robot events, task/order/shipment/stock updates.
import type { WebSocketMessage } from '../types'
import { useLiveStore } from '../stores/liveStore'
import { BACKEND_ORIGIN } from '../api/client'

type Listener = (msg: WebSocketMessage) => void

const listeners = new Set<Listener>()
let ws: WebSocket | null = null
let reconnectTimer: number | null = null
let closeTimer: number | null = null

function connect() {
  if (ws) return
  const token = localStorage.getItem('access_token') || ''
  const base = BACKEND_ORIGIN
    ? BACKEND_ORIGIN.replace(/^http/, 'ws') // https://x.up.railway.app -> wss://x.up.railway.app
    : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000`
  const socket = new WebSocket(`${base}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`)
  ws = socket
  socket.onopen = () => useLiveStore.getState().setConnected(true)
  socket.onerror = () => {}
  socket.onclose = () => {
    if (ws !== socket) return // superseded socket (StrictMode remount)
    ws = null
    useLiveStore.getState().setConnected(false)
    if (listeners.size) reconnectTimer = window.setTimeout(connect, 3000)
  }
  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as WebSocketMessage
      useLiveStore.getState().apply(msg.type, msg.data)
      listeners.forEach((l) => l(msg))
    } catch {
      // ignore malformed messages
    }
  }
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  if (closeTimer) window.clearTimeout(closeTimer)
  connect()
  return () => {
    listeners.delete(listener)
    if (!listeners.size) {
      closeTimer = window.setTimeout(() => {
        if (listeners.size) return
        if (reconnectTimer) window.clearTimeout(reconnectTimer)
        const s = ws
        ws = null
        s?.close()
        useLiveStore.getState().setConnected(false)
      }, 1500)
    }
  }
}

export function send(type: string, data: Record<string, unknown>): boolean {
  if (ws?.readyState !== WebSocket.OPEN) return false
  ws.send(JSON.stringify({ type, data }))
  return true
}
