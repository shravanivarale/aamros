import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, Camera, Video, Radio, Edit3, Trash2, Globe } from 'lucide-react'
import { api } from '../../api/client'
import { Card, StatusBadge, LoadingSpinner, EmptyState, Button, Modal, Input, IconButton } from '../../components/ui'
import type { Robot } from '../../types'
import { useLiveStore } from '../../stores/liveStore'
import { batteryLabel } from '../../utils/format'

export function RobotsPage() {
  const liveRobots = useLiveStore((st) => st.robots)
  const queryClient = useQueryClient()
  
  // Modals state
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [editingRobot, setEditingRobot] = useState<Robot | null>(null)
  const [deletingRobot, setDeletingRobot] = useState<Robot | null>(null)

  // Register Form
  const [name, setName] = useState('')
  const [model, setModel] = useState('AMR-V2')
  const [serialNumber, setSerialNumber] = useState('')
  const [ipAddress, setIpAddress] = useState('192.168.1.12')

  // Edit Form
  const [editName, setEditName] = useState('')
  const [editModel, setEditModel] = useState('')
  const [editSerial, setEditSerial] = useState('')
  const [editIp, setEditIp] = useState('')

  const [isCameraActive, setIsCameraActive] = useState(true)
  const [streamFailed, setStreamFailed] = useState(false)

  const { data: robots, isLoading } = useQuery({
    queryKey: ['robots'],
    queryFn: api.robots.list,
  })

  // Mutations
  const registerMutation = useMutation({
    mutationFn: api.robots.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robots'] })
      setIsRegisterOpen(false)
      setName('')
      setSerialNumber('')
      setIpAddress('192.168.1.12')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Robot> }) => api.robots.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robots'] })
      setEditingRobot(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.robots.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robots'] })
      setDeletingRobot(null)
    },
  })

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !serialNumber) return
    registerMutation.mutate({ name, model, serial_number: serialNumber, ip_address: ipAddress })
  }

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingRobot) return
    updateMutation.mutate({
      id: editingRobot.id,
      data: {
        name: editName,
        model: editModel,
        serial_number: editSerial,
        ip_address: editIp,
      },
    })
  }

  const openEditModal = (robot: Robot) => {
    setEditingRobot(robot)
    setEditName(robot.name)
    setEditModel(robot.model)
    setEditSerial(robot.serial_number)
    setEditIp(robot.ip_address || '192.168.1.12')
  }

  if (isLoading) return <LoadingSpinner />

  const activeRobot = robots && robots.length > 0 ? robots[0] : null
  const currentIp = activeRobot?.ip_address || 'robot'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-page-title">Autonomous Robot Fleet</h1>
          <p className="text-xs text-text-secondary">Monitor, manage and configure autonomous mobile robots (AMRs)</p>
        </div>
        <Button variant="secondary" icon={<Bot className="h-4 w-4" />} onClick={() => setIsRegisterOpen(true)}>
          Register AMR Robot
        </Button>
      </div>

      {/* Live Camera Stream Viewer Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Video className="h-4 w-4 text-cyan" />
            <h3 className="text-sm font-bold text-text-primary">Live AMR Camera Feed ({currentIp}:8005)</h3>
            {isCameraActive && !streamFailed && (
              <span className="neu-inset inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold text-success">
                <Radio className="h-3 w-3 motion-safe:animate-pulse" aria-hidden="true" /> LIVE
              </span>
            )}
          </div>
          <Button
            variant="outline"
            className="text-xs py-1"
            onClick={() => {
              setStreamFailed(false)
              setIsCameraActive(!isCameraActive)
            }}
          >
            <Camera className="h-3.5 w-3.5 mr-1" />
            {isCameraActive ? 'Pause Stream' : 'Resume Stream'}
          </Button>
        </div>

        <div className="relative aspect-video max-h-[380px] w-full overflow-hidden neu-inset flex items-center justify-center">
          {isCameraActive && !streamFailed && (
            <img
              src={api.robotCommunication.videoUrl(activeRobot?.id)}
              alt="AMR live camera stream"
              className="h-full w-full object-contain"
              onError={() => setStreamFailed(true)}
            />
          )}

          <div className={`space-y-2 p-6 text-center ${isCameraActive && !streamFailed ? 'hidden' : ''}`}>
            <Camera className="mx-auto h-10 w-10 text-text-secondary" aria-hidden="true" />
            <p className="text-xs font-mono text-text-secondary">
              {!isCameraActive ? 'Camera feed paused.' : `No camera frames received from ${currentIp}:8005.`}
            </p>
            <p className="text-[10px] text-text-secondary font-mono">
              ROS Topic: /camera/image_raw (sensor_msgs/Image)
            </p>
          </div>
        </div>
      </Card>

      {!robots?.length ? (
        <EmptyState title="No Robots in Fleet" description="Register robots to begin autonomous operations." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {robots.map((robot) => {
            const lv = liveRobots[robot.id]
            return (
            <Card key={robot.id} className="space-y-4 relative group">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="neu-inset flex h-10 w-10 items-center justify-center text-action-primary">
                    <Bot className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text-primary">{robot.name}</h3>
                    <p className="text-[11px] text-text-secondary font-mono">{robot.model} · {robot.serial_number}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={lv?.status ?? robot.status} />
                  <div className="flex items-center gap-1">
                    <IconButton label={`Edit ${robot.name}`} className="h-9 w-9" onClick={() => openEditModal(robot)}>
                      <Edit3 className="h-4 w-4" />
                    </IconButton>
                    <IconButton label={`Delete ${robot.name}`} className="h-9 w-9 hover:text-error" onClick={() => setDeletingRobot(robot)}>
                      <Trash2 className="h-4 w-4" />
                    </IconButton>
                  </div>
                </div>
              </div>

              <div className="p-2 rounded bg-bg-secondary border border-border-primary flex items-center justify-between text-xs font-mono">
                <span className="text-text-secondary flex items-center gap-1">
                  <Globe className="h-3.5 w-3.5 text-cyan" /> Robot IP:
                </span>
                <span className="font-bold text-cyan">{robot.ip_address || 'unknown'}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
                  <span className="text-text-secondary block text-[10px] uppercase font-mono">Battery</span>
                  <span className="font-semibold text-text-primary font-mono">{batteryLabel(lv?.battery_known === false ? -1 : lv?.battery_level ?? robot.battery_level, 1)}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
                  <span className="text-text-secondary block text-[10px] uppercase font-mono">Enabled</span>
                  <span className={`font-semibold ${robot.is_enabled ? 'text-success' : 'text-error'}`}>
                    {robot.is_enabled ? 'Active' : 'Disabled'}
                  </span>
                </div>
              </div>

              {(lv?.x ?? robot.position_x) != null && (
                <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-primary text-xs font-mono">
                  <span className="text-text-secondary block text-[10px] uppercase">
                    Live position on map {lv ? (lv.localized ? '· localized' : '· NOT localized') : '· last known'}
                  </span>
                  <span className="text-cyan">
                    X: {(lv?.x ?? robot.position_x)!.toFixed(2)} | Y: {(lv?.y ?? robot.position_y)?.toFixed(2)} | θ:{' '}
                    {lv?.yaw != null ? `${((lv.yaw * 180) / Math.PI).toFixed(0)}°` : '—'}
                    {lv?.linear_velocity != null && ` | v: ${lv.linear_velocity.toFixed(2)} m/s`}
                  </span>
                </div>
              )}
            </Card>
            )
          })}
        </div>
      )}

      {/* Register Robot Modal */}
      <Modal isOpen={isRegisterOpen} onClose={() => setIsRegisterOpen(false)} title="Register Autonomous Mobile Robot (AMR)">
        <form onSubmit={handleRegisterSubmit} className="space-y-4">
          <Input label="Robot Name" placeholder="e.g. AMR-004 Fleet Scout" value={name} onChange={setName} required />
          <Input label="Robot IP Address" placeholder="e.g. 192.168.1.12" value={ipAddress} onChange={setIpAddress} required />
          <Input label="Model / Spec" placeholder="e.g. AMR-V2 Heavy Payload" value={model} onChange={setModel} required />
          <Input label="Serial Number" placeholder="e.g. SN-AMR-2026-981" value={serialNumber} onChange={setSerialNumber} required />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setIsRegisterOpen(false)} type="button">Cancel</Button>
            <Button type="submit" disabled={registerMutation.isPending}>
              {registerMutation.isPending ? 'Registering...' : 'Register AMR'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Robot Modal */}
      <Modal isOpen={!!editingRobot} onClose={() => setEditingRobot(null)} title={`Edit Robot - ${editingRobot?.name}`}>
        <form onSubmit={handleEditSubmit} className="space-y-4">
          <Input label="Robot Name" value={editName} onChange={setEditName} required />
          <Input label="Robot IP Address" value={editIp} onChange={setEditIp} required />
          <Input label="Model / Spec" value={editModel} onChange={setEditModel} required />
          <Input label="Serial Number" value={editSerial} onChange={setEditSerial} required />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setEditingRobot(null)} type="button">Cancel</Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal isOpen={!!deletingRobot} onClose={() => setDeletingRobot(null)} title="Delete Robot">
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to remove <strong className="text-text-primary">{deletingRobot?.name}</strong> ({deletingRobot?.ip_address}) from your fleet?
          </p>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setDeletingRobot(null)}>Cancel</Button>
            <Button
              variant="outline"
              className="border-error text-error hover:bg-error/10"
              onClick={() => deletingRobot && deleteMutation.mutate(deletingRobot.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
