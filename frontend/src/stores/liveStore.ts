import { create } from 'zustand'

export interface LiveRobot {
  id: string
  x?: number
  y?: number
  yaw?: number
  status?: string
  battery_level?: number
  battery_known?: boolean
  localized?: boolean
  estop?: boolean
  allow_motion?: boolean
  connectivity?: string
  current_task_id?: string | null
  linear_velocity?: number
  angular_velocity?: number
  trail: [number, number][]
  path?: [number, number][] // route the robot planned for its current leg (map frame, metres)
  updatedAt: number
}

export interface LiveEvent {
  seq?: number
  robot_id: string
  task_id?: string | null
  message_type: string
  timestamp?: string
  payload?: Record<string, unknown>
}

interface LiveState {
  connected: boolean
  robots: Record<string, LiveRobot>
  events: LiveEvent[]
  lastCommandError: string | null
  setConnected: (c: boolean) => void
  apply: (type: string, data: Record<string, any>) => void
}

const TRAIL_MAX = 300

export const useLiveStore = create<LiveState>((set) => ({
  connected: false,
  robots: {},
  events: [],
  lastCommandError: null,
  setConnected: (connected) => set({ connected }),
  apply: (type, d) =>
    set((s) => {
      const id = d.robot_id as string | undefined
      if (type === 'robot_position' && id) {
        const prev = s.robots[id] ?? { id, trail: [], updatedAt: 0 }
        const last = prev.trail[prev.trail.length - 1]
        const moved = !last || Math.hypot(d.x - last[0], d.y - last[1]) > 0.05
        const trail = moved ? [...prev.trail, [d.x, d.y] as [number, number]].slice(-TRAIL_MAX) : prev.trail
        return {
          robots: {
            ...s.robots,
            [id]: { ...prev, x: d.x, y: d.y, yaw: d.yaw, localized: d.localized, linear_velocity: d.linear_velocity,
              angular_velocity: d.angular_velocity, trail, updatedAt: Date.now() },
          },
        }
      }
      if (type === 'robot_status' && id) {
        const prev = s.robots[id] ?? { id, trail: [], updatedAt: 0 }
        const offline = d.status === 'offline'
        return {
          robots: {
            ...s.robots,
            [id]: { ...prev, status: d.status, battery_level: d.battery_level, battery_known: d.battery_known, localized: d.localized,
              estop: d.estop, allow_motion: d.allow_motion, connectivity: d.connectivity, current_task_id: d.current_task_id,
              ...(offline ? { x: undefined, y: undefined, path: undefined } : {}), updatedAt: Date.now() },
          },
        }
      }
      if (type === 'robot_event') {
        const ev = d as LiveEvent
        const robots = { ...s.robots }
        if (id && ev.message_type === 'PATH_PLANNED') {
          const pts = ((ev.payload?.waypoints as number[][]) ?? []).map((p) => [p[0], p[1]] as [number, number])
          robots[id] = { ...(robots[id] ?? { id, trail: [], updatedAt: 0 }), path: pts }
        }
        if (id && ['TASK_COMPLETED', 'TASK_FAILED', 'TASK_CANCELLED'].includes(ev.message_type) && robots[id]) {
          robots[id] = { ...robots[id], path: undefined, trail: [] }
        }
        return { robots, events: [ev, ...s.events].slice(0, 200) }
      }
      if (type === 'command_error') return { lastCommandError: `${d.command}: ${d.error}` }
      return {}
    }),
}))
