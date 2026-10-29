import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { subscribe } from '../lib/liveSocket'

// Which cached queries a live message makes stale. Throttled per key so a burst of messages causes one refetch.
const INVALIDATE: Record<string, string[][]> = {
  robot_status: [['robots'], ['robot-communication-robots'], ['robot-communication-health'], ['bridges']],
  robot_event: [['robot-communication-events'], ['robot-events']],
  task_update: [['robot-communication-events'], ['orders'], ['shipments'], ['robot-tasks']],
  order_update: [['orders']],
  shipment_update: [['shipments']],
  inventory_update: [['inventory'], ['products'], ['stock-movements']],
  map_update: [['map'], ['map-current']],
  locations_update: [['locations']],
}

/** Mount once (AppLayout): keeps every page's data in step with what the robot and backend are doing, without polling. */
export function useLiveSync() {
  const qc = useQueryClient()
  useEffect(() => {
    const last = new Map<string, number>()
    return subscribe((msg) => {
      for (const key of INVALIDATE[msg.type] ?? []) {
        const k = key.join('/')
        const now = Date.now()
        if (now - (last.get(k) ?? 0) < 800) continue
        last.set(k, now)
        qc.invalidateQueries({ queryKey: key })
      }
    })
  }, [qc])
}
