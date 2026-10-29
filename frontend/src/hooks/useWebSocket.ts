import { useEffect, useRef, useCallback } from 'react'
import type { WebSocketMessage } from '../types'
import { send, subscribe } from '../lib/liveSocket'
import { useLiveStore } from '../stores/liveStore'

interface WebSocketOptions {
  onMessage?: (msg: WebSocketMessage) => void
  onRobotPosition?: (data: any) => void
  onRobotStatus?: (data: any) => void
  onRobotEvent?: (data: any) => void
  onTaskUpdate?: (data: any) => void
  onInventoryUpdate?: (data: any) => void
  onOrderUpdate?: (data: any) => void
  onShipmentUpdate?: (data: any) => void
  onMapUpdate?: (data: any) => void
  onLocationsUpdate?: (data: any) => void
}

/** Subscribe to the shared live socket. Same API as before; `isConnected` reflects the one shared connection. */
export function useWebSocket(options: WebSocketOptions = {}) {
  const isConnected = useLiveStore((s) => s.connected)
  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  }, [options])

  useEffect(() => {
    return subscribe((msg) => {
      const o = optionsRef.current
      o.onMessage?.(msg)
      switch (msg.type) {
        case 'robot_position': o.onRobotPosition?.(msg.data); break
        case 'robot_status': o.onRobotStatus?.(msg.data); break
        case 'robot_event': o.onRobotEvent?.(msg.data); break
        case 'task_update': o.onTaskUpdate?.(msg.data); break
        case 'inventory_update': o.onInventoryUpdate?.(msg.data); break
        case 'order_update': o.onOrderUpdate?.(msg.data); break
        case 'shipment_update': o.onShipmentUpdate?.(msg.data); break
        case 'map_update': o.onMapUpdate?.(msg.data); break
        case 'locations_update': o.onLocationsUpdate?.(msg.data); break
      }
    })
  }, [])

  const sendCommand = useCallback((type: string, data: Record<string, unknown>) => send(type, data), [])
  return { isConnected, sendCommand }
}
