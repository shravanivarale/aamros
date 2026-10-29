import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ListTodo, CheckCircle, Clock, Plus, Radio, XCircle, Activity } from 'lucide-react'
import { api } from '../../api/client'
import { Card, StatusBadge, DataTable, type Column, Button, Modal, Input, Select } from '../../components/ui'

export function RobotTasksPage() {
  const queryClient = useQueryClient()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [sourceLoc, setSourceLoc] = useState('')
  const [destLoc, setDestLoc] = useState('')
  const [taskType, setTaskType] = useState('PICK_AND_PLACE')
  const [priority, setPriority] = useState('10')

  // Locations taught on the real map: a task can only go where the robot knows how to get to
  const { data: locations = [] } = useQuery({ queryKey: ['locations'], queryFn: api.locations.list })
  const locOptions = [{ value: '', label: locations.length ? 'Select a location…' : 'No locations taught yet (Warehouse Map → Locations)' },
    ...locations.map((l) => ({ value: l.code, label: `${l.code} · ${l.kind}${l.issue ? ' (robot rejected it)' : ''}` }))]

  // Fetch ROS Bridge Health
  const { data: healthData } = useQuery({
    queryKey: ['robot-communication-health'],
    queryFn: api.robotCommunication.health,
    refetchInterval: 15000, // live updates arrive over the WebSocket (useLiveSync); this is only a safety net
  })

  // Fetch Live Events Log from ROS Bridge
  const { data: eventsData = [] } = useQuery({
    queryKey: ['robot-communication-events'],
    queryFn: api.robotCommunication.listEvents,
    refetchInterval: 15000,
  })

  // Fetch Robots List
  const { data: robotsData = [] } = useQuery({
    queryKey: ['robot-communication-robots'],
    queryFn: api.robotCommunication.listRobots,
    refetchInterval: 15000,
  })

  // Submit Mission Mutation
  const submitMutation = useMutation({
    mutationFn: api.robotCommunication.submitTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robot-communication-events'] })
      queryClient.invalidateQueries({ queryKey: ['robot-communication-health'] })
      setIsModalOpen(false)
    },
  })

  // Cancel Task Mutation
  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => api.robotCommunication.cancelTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['robot-communication-events'] })
    },
  })

  const handleCreateTask = (e: React.FormEvent) => {
    e.preventDefault()
    submitMutation.mutate({
      task_type: taskType,
      source_location_id: sourceLoc,
      destination_location_id: destLoc,
      priority: parseInt(priority) || 10,
    })
  }

  const columns: Column<Record<string, unknown>>[] = [
    {
      header: 'Message / Task ID',
      cell: (row) => (
        <div>
          <span className="font-mono text-cyan text-xs font-semibold">{String(row.task_id || row.message_id || 'N/A').slice(0, 13)}...</span>
          <span className="block text-[10px] text-text-secondary">{String(row.timestamp || '')}</span>
        </div>
      ),
    },
    {
      header: 'Event / Type',
      cell: (row) => (
        <span className="font-mono text-xs text-text-primary uppercase font-bold px-2 py-0.5 rounded bg-bg-secondary border border-border-primary">
          {String(row.message_type || row.task_type || 'EVENT')}
        </span>
      ),
    },
    {
      header: 'Source -> Destination',
      cell: (row) => {
        const payload = (row.payload as Record<string, unknown>) || {}
        const src = (payload.source_location as Record<string, unknown>)?.location_id || 'RACK-1'
        const dst = (payload.destination_location as Record<string, unknown>)?.location_id || 'SHIP-11'
        return (
          <span className="text-xs font-mono text-text-primary">
            {String(src)} → {String(dst)}
          </span>
        )
      },
    },
    {
      header: 'Status',
      cell: (row) => <StatusBadge status={String(row.message_type || 'QUEUED')} />,
    },
    {
      header: 'Actions',
      cell: (row) => {
        const taskId = String(row.task_id || '')
        if (!taskId) return null
        return (
          <Button
            variant="ghost"
            className="text-error hover:bg-error/10 text-xs py-1"
            onClick={() => cancelMutation.mutate(taskId)}
          >
            <XCircle className="h-3.5 w-3.5 mr-1" />
            Cancel
          </Button>
        )
      },
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="t-page-title">ROS 2 Robot Task Pipeline</h1>
          <p className="text-xs text-text-secondary">Bidirectional WMS JSON Message Pipeline & Real-Time Telemetry Bridge</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Dispatch ROS 2 Mission
        </Button>
      </div>

      {/* Health & Telemetry Header Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-cyan/10 text-cyan">
            <Radio className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono text-text-secondary">Bridge Health</p>
            <p className="text-sm font-bold text-text-primary uppercase font-mono">
              {healthData?.status || 'Active'}
            </p>
          </div>
        </Card>

        <Card className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-amber/10 text-amber">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono text-text-secondary">Pending Tasks</p>
            <p className="text-lg font-bold text-text-primary font-mono">{healthData?.pending_tasks || 0} Queued</p>
          </div>
        </Card>

        <Card className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-success/10 text-success">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono text-text-secondary">Active AMRs</p>
            <p className="text-lg font-bold text-text-primary font-mono">{robotsData.length} Robot(s)</p>
          </div>
        </Card>

        <Card className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-purple/10 text-purple">
            <CheckCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono text-text-secondary">ROS Node</p>
            <p className="text-xs font-bold text-text-primary font-mono">wms_bridge v2.0</p>
          </div>
        </Card>
      </div>

      {/* ROS 2 Event Stream & Tasks Table */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <ListTodo className="h-4 w-4 text-cyan" />
            Live ROS 2 Event & Task Lifecycle Log
          </h3>
        </div>
        <DataTable columns={columns} data={(Array.isArray(eventsData) ? eventsData : []) as unknown as Record<string, unknown>[]} />
      </Card>

      {/* Dispatch Mission Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Dispatch ROS 2 Robot Mission">
        <form onSubmit={handleCreateTask} className="space-y-4">
          <Select
            label="Task Mission Type"
            value={taskType}
            onChange={(val) => setTaskType(val)}
            options={[
              { value: 'PICK_AND_PLACE', label: 'PICK_AND_PLACE (Full Autonomous Cycle)' },
              { value: 'PICK', label: 'PICK (Retrieve SKU from Rack)' },
              { value: 'PLACE', label: 'PLACE (Drop SKU off at Rack/Slot)' },
              { value: 'RELOCATE', label: 'RELOCATE (Reslotting Optimization)' },
            ]}
          />

          <div className="grid grid-cols-2 gap-4">
            <Select label="Source location" value={sourceLoc} onChange={setSourceLoc} options={locOptions} />
            <Select label="Destination location" value={destLoc} onChange={setDestLoc} options={locOptions} />
          </div>

          <Input
            label="Task Priority (1-20)"
            type="number"
            value={priority}
            onChange={(val) => setPriority(val)}
            required
          />
          {submitMutation.isError && (
            <p role="alert" className="text-xs text-error font-mono">{(submitMutation.error as Error).message}</p>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitMutation.isPending || !sourceLoc || !destLoc}>
              {submitMutation.isPending ? 'Publishing to ROS...' : 'Publish Mission Envelope'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
