import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useLiveStore } from '../../stores/liveStore'
import { drawMapToCanvas, type MapData, type MapView } from '../../utils/mapRenderer'
import type { MapLocation } from '../../types'

const KIND_COLOR: Record<string, string> = {
  home: '#22c55e', receiving: '#f59e0b', shipping: '#a855f7', charging: '#eab308', rack_slot: '#38bdf8', waypoint: '#94a3b8',
}

export interface PickedPose {
  x: number
  y: number
  yaw: number // radians
}

interface Props {
  mapData?: MapData | null
  locations?: MapLocation[]
  /** When set, press-and-drag on the map picks a pose (position + heading) and calls this on release. */
  onPick?: (pose: PickedPose) => void
  pending?: PickedPose | null
  className?: string
  height?: number
}

/** The real map with live robots (from the WebSocket), their planned routes and the taught locations on top. */
export function LiveMap({ mapData, locations = [], onPick, pending, className = '', height = 520 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const viewRef = useRef<MapView | null>(null)
  const dragRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const robots = useLiveStore((s) => s.robots)
  const { data: robotRows } = useQuery({ queryKey: ['robots'], queryFn: api.robots.list })

  // keep the latest values readable from the animation loop without restarting it
  const live = useRef({ mapData, locations, robots, names: {} as Record<string, string>, pending, onPick })
  live.current = {
    mapData, locations, robots, pending, onPick,
    names: Object.fromEntries((robotRows ?? []).map((r) => [r.id, r.name])),
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    let raf = 0

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(height * dpr)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const draw = () => {
      const { mapData: m, locations: locs, robots: rs, names, pending: pend } = live.current
      const dpr = window.devicePixelRatio || 1
      const w = canvas.width / dpr
      const h = canvas.height / dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const view = drawMapToCanvas(ctx, w, h, m)
      viewRef.current = view
      if (view) {
        for (const l of locs) drawLocation(ctx, view, l)
        if (pend) drawPose(ctx, view, pend, '#ef4444', 0.45)
        for (const r of Object.values(rs)) drawRobot(ctx, view, r, names[r.id] ?? 'robot')
        const d = dragRef.current
        if (d) {
          ctx.strokeStyle = '#ef4444'
          ctx.lineWidth = 3
          const [sx, sy] = view.toCanvas(d.x, d.y)
          ctx.beginPath()
          ctx.moveTo(sx, sy)
          ctx.lineTo(d.px, d.py)
          ctx.stroke()
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
    }
  }, [height])

  const pos = (e: React.PointerEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect()
    return [e.clientX - rect.left, e.clientY - rect.top] as const
  }

  return (
    <canvas
      ref={canvasRef}
      className={`w-full rounded-lg ${onPick ? 'cursor-crosshair' : ''} ${className}`}
      style={{ height, touchAction: 'none' }}
      onPointerDown={(e) => {
        const view = viewRef.current
        if (!onPick || !view) return
        e.currentTarget.setPointerCapture(e.pointerId)
        const [px, py] = pos(e)
        const [x, y] = view.toWorld(px, py)
        dragRef.current = { x, y, px, py }
      }}
      onPointerMove={(e) => {
        if (dragRef.current) [dragRef.current.px, dragRef.current.py] = pos(e)
      }}
      onPointerUp={(e) => {
        const view = viewRef.current
        const d = dragRef.current
        dragRef.current = null
        if (!onPick || !view || !d) return
        const [px, py] = pos(e)
        const [x1, y1] = view.toWorld(px, py)
        const moved = Math.hypot(x1 - d.x, y1 - d.y) > 0.15
        onPick({ x: +d.x.toFixed(2), y: +d.y.toFixed(2), yaw: moved ? Math.atan2(y1 - d.y, x1 - d.x) : 0 })
      }}
    />
  )
}

/** Light text with a dark outline: readable on both the white floor and the dark background of the map. */
function haloText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number) {
  ctx.save()
  ctx.lineJoin = 'round'
  ctx.lineWidth = 4
  ctx.strokeStyle = 'rgba(2,6,23,0.95)'
  ctx.strokeText(text, x, y)
  ctx.fillStyle = '#f8fafc'
  ctx.fillText(text, x, y)
  ctx.restore()
}

function drawPose(ctx: CanvasRenderingContext2D, view: MapView, p: PickedPose, color: string, len = 0.5) {
  const [cx, cy] = view.toCanvas(p.x, p.y)
  const L = len * view.pxPerMetre
  ctx.save()
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = 3
  ctx.beginPath()
  ctx.moveTo(cx, cy)
  ctx.lineTo(cx + L * Math.cos(p.yaw), cy - L * Math.sin(p.yaw))
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(cx, cy, 6, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function drawLocation(ctx: CanvasRenderingContext2D, view: MapView, l: MapLocation) {
  const [cx, cy] = view.toCanvas(l.x, l.y)
  const color = l.issue ? '#ef4444' : KIND_COLOR[l.kind] ?? '#94a3b8'
  ctx.save()
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = 2
  const L = 0.35 * view.pxPerMetre
  ctx.beginPath()
  ctx.moveTo(cx, cy)
  ctx.lineTo(cx + L * Math.cos(l.yaw), cy - L * Math.sin(l.yaw))
  ctx.stroke()
  ctx.beginPath()
  ctx.rect(cx - 6, cy - 6, 12, 12)
  ctx.globalAlpha = 0.85
  ctx.fill()
  ctx.globalAlpha = 1
  ctx.font = 'bold 11px monospace'
  ctx.textAlign = 'left'
  haloText(ctx, l.code + (l.issue ? ' ⚠' : ''), cx + 9, cy - 8)
  ctx.restore()
}

function drawRobot(ctx: CanvasRenderingContext2D, view: MapView, r: ReturnType<typeof useLiveStore.getState>['robots'][string], name: string) {
  if (r.x == null || r.y == null || r.yaw == null) return
  ctx.save()
  if (r.trail.length > 1) {
    ctx.strokeStyle = 'rgba(14,165,233,0.45)'
    ctx.lineWidth = 2
    ctx.beginPath()
    r.trail.forEach(([x, y], i) => {
      const [px, py] = view.toCanvas(x, y)
      if (i) ctx.lineTo(px, py)
      else ctx.moveTo(px, py)
    })
    ctx.stroke()
  }
  if (r.path && r.path.length > 1) {
    ctx.strokeStyle = '#f59e0b'
    ctx.setLineDash([8, 5])
    ctx.lineWidth = 2.5
    ctx.beginPath()
    r.path.forEach(([x, y], i) => {
      const [px, py] = view.toCanvas(x, y)
      if (i) ctx.lineTo(px, py)
      else ctx.moveTo(px, py)
    })
    ctx.stroke()
    ctx.setLineDash([])
  }
  // chassis 0.56 m long x 0.45 m wide about the rotation centre
  const [cx, cy] = view.toCanvas(r.x, r.y)
  const k = view.pxPerMetre
  ctx.translate(cx, cy)
  ctx.rotate(-r.yaw)
  const stopped = r.estop || r.status === 'emergency_stop'
  ctx.fillStyle = stopped ? 'rgba(239,68,68,0.45)' : r.localized ? 'rgba(14,165,233,0.45)' : 'rgba(148,163,184,0.45)'
  ctx.strokeStyle = stopped ? '#ef4444' : r.localized ? '#0ea5e9' : '#94a3b8'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.rect(-0.28 * k, -0.225 * k, 0.56 * k, 0.45 * k)
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.moveTo(0.3 * k, 0)
  ctx.lineTo(0.05 * k, 0.12 * k)
  ctx.lineTo(0.05 * k, -0.12 * k)
  ctx.closePath()
  ctx.fill()
  ctx.rotate(r.yaw)
  ctx.font = 'bold 12px monospace'
  ctx.textAlign = 'center'
  haloText(ctx, `${name}${r.localized ? '' : ' (not localized)'}`, 0, -0.4 * k - 4)
  ctx.restore()
}
