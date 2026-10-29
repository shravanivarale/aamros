import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertOctagon, Battery, Navigation, Activity, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useLiveStore } from '../../stores/liveStore'
import { Button, StatusBadge, LoadingSpinner } from '../../components/ui'
import { LiveMap } from '../../components/map/LiveMap'
import { batteryLabel } from '../../utils/format'

export function OperatorPortal() {
  const { data: mapData, isLoading: mapLoading } = useQuery({
    queryKey: ['map', 'current'],
    queryFn: api.map.getCurrent,
  })
  const { data: locations = [] } = useQuery({ queryKey: ['locations'], queryFn: api.locations.list })
  const { data: robots, isLoading: robotsLoading } = useQuery({
    queryKey: ['robots'],
    queryFn: api.robots.list,
  })

  const [activeRobotId, setActiveRobotId] = useState<string | null>(null)
  const live = useLiveStore((s) => s.robots)
  const commandError = useLiveStore((s) => s.lastCommandError)
  const { sendCommand, isConnected } = useWebSocket()

  if (robotsLoading || mapLoading) return <LoadingSpinner />

  const activeRobot = robots?.find((r) => r.id === activeRobotId)
  const lv = activeRobotId ? live[activeRobotId] : undefined
  const status = lv?.status ?? activeRobot?.status
  const battery = lv?.battery_known === false ? -1 : lv?.battery_level ?? activeRobot?.battery_level

  const handleMove = (direction: string) => {
    if (!activeRobot) return
    let linear = 0
    let angular = 0
    switch (direction) {
      case 'up': linear = 0.3; break
      case 'down': linear = -0.2; break
      case 'left': angular = 0.8; break
      case 'right': angular = -0.8; break
    }
    // each press is a short jog: the robot stops by itself 0.4 s after the last command
    sendCommand('manual_velocity', { robot_id: activeRobot.id, linear_v: linear, angular_v: angular })
  }

  return (
    <div className="flex h-full flex-col gap-6 lg:flex-row">
      <div className="neu-raised relative flex min-h-[22rem] flex-1 flex-col overflow-hidden">
        <div className="p-4 border-b border-border-primary flex justify-between items-center bg-bg-primary/50">
          <h2 className="font-semibold text-text-primary flex items-center gap-2">
            <Navigation className="h-4 w-4 text-cyan" />
            Live Fleet Map
          </h2>
          <span className="text-xs text-text-secondary">
            {isConnected ? 'live' : 'reconnecting…'}
            {mapData && ` · ${mapData.label} · ${mapData.resolution} m/px`}
          </span>
        </div>
        <div className="relative flex-1 bg-bg-secondary shadow-[var(--neu-inset)] p-2">
          <LiveMap mapData={mapData} locations={locations} height={560} />
        </div>
      </div>

      <div className="flex w-full flex-col gap-4 lg:w-80">
        <div className="neu-raised p-4">
          <h3 className="font-semibold text-text-primary mb-3">Select Robot</h3>
          <div className="space-y-2">
            {robots?.map((robot) => (
              <button
                key={robot.id}
                onClick={() => setActiveRobotId(robot.id)}
                aria-pressed={activeRobotId === robot.id}
                className="neu-pressable flex min-h-10 w-full cursor-pointer items-center justify-between rounded-[var(--radius-neu-sm)] px-3 py-2 text-left text-sm text-text-primary"
              >
                <span>{robot.name}</span>
                <StatusBadge status={live[robot.id]?.status ?? robot.status} />
              </button>
            ))}
            {!robots?.length && <p className="text-xs text-text-secondary">No robots yet. The robot appears here as soon as its bridge connects.</p>}
          </div>
        </div>

        {activeRobot && (
          <div className="neu-raised flex-1 flex flex-col">
            <div className="p-4 border-b border-border-primary">
              <h3 className="font-semibold text-text-primary">{activeRobot.name} Telemetry</h3>
            </div>

            <div className="p-4 space-y-4 flex-1">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="neu-inset p-3">
                  <div className="text-text-secondary text-xs flex items-center gap-1 mb-1">
                    <Battery className="h-3 w-3" /> Battery
                  </div>
                  <div className="text-text-primary font-medium">{batteryLabel(battery, 1)}</div>
                </div>
                <div className="neu-inset p-3">
                  <div className="text-text-secondary text-xs flex items-center gap-1 mb-1">
                    <Activity className="h-3 w-3" /> Status
                  </div>
                  <div className="text-text-primary font-medium capitalize">{status}</div>
                </div>
              </div>

              <div className="neu-inset p-3 text-sm">
                <div className="text-text-secondary text-xs mb-1 flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3" /> Pose on map {lv?.localized ? '(localized)' : '(not localized)'}
                </div>
                {lv?.x != null ? (
                  <div className="font-mono text-cyan text-xs">
                    X: {lv.x.toFixed(2)} m <br />
                    Y: {lv.y?.toFixed(2)} m <br />
                    θ: {(((lv.yaw ?? 0) * 180) / Math.PI).toFixed(0)}° <br />
                    v: {(lv.linear_velocity ?? 0).toFixed(2)} m/s
                  </div>
                ) : (
                  <div className="font-mono text-xs text-text-secondary">No pose: robot offline or not localized.</div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-border-primary">
                <h4 className="text-xs font-medium text-text-secondary mb-3">Manual Control</h4>
                {lv?.allow_motion === false && (
                  <p className="text-xs text-text-secondary mb-3">Motion is disabled on the robot bridge (start it with allow_motion:=true).</p>
                )}

                <div className="grid grid-cols-3 gap-2 w-48 mx-auto mb-6">
                  <div />
                  <Button variant="secondary" aria-label="Move forward" className="h-12 p-2" onClick={() => handleMove('up')}>↑</Button>
                  <div />
                  <Button variant="secondary" aria-label="Rotate left" className="h-12 p-2" onClick={() => handleMove('left')}>⟲</Button>
                  <Button variant="secondary" aria-label="Move backward" className="h-12 p-2" onClick={() => handleMove('down')}>↓</Button>
                  <Button variant="secondary" aria-label="Rotate right" className="h-12 p-2" onClick={() => handleMove('right')}>⟳</Button>
                </div>

                <Button variant="danger" className="w-full" onClick={() => sendCommand('emergency_stop', { robot_id: activeRobot.id })}>
                  <AlertOctagon className="h-4 w-4 mr-2" />
                  EMERGENCY STOP
                </Button>
                {(lv?.estop || status === 'emergency_stop') && (
                  <Button variant="secondary" className="w-full mt-2" onClick={() => sendCommand('clear_estop', { robot_id: activeRobot.id })}>
                    Release emergency stop
                  </Button>
                )}
                {commandError && <p role="alert" className="mt-2 text-xs text-error font-mono">{commandError}</p>}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
