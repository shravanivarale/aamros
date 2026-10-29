import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit3, Trash2, Zap, Boxes, ExternalLink, RefreshCw, Map, Layers, CheckCircle2 } from 'lucide-react'
import { api } from '../../api/client'
import { Card, DataTable, type Column, Button, Modal, Input, Select } from '../../components/ui'

interface RackItem extends Record<string, unknown> {
  id: string
  code: string
  zone: string
  levels: number
  slots: number
  occupiedSlots: number
  slotScore: number
  assignedSkus: string
  maxWeight: string
  status: string
}

export function RacksPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<RackItem | null>(null)

  // Map-adaptable input state
  const [code, setCode] = useState('')
  const [zone, setZone] = useState('Golden Fast-Picking')
  const [shelvesCount, setShelvesCount] = useState('4')
  const [slotsPerShelf, setSlotsPerShelf] = useState('4')
  const [maxWeight, setMaxWeight] = useState('500 kg')
  const [status, setStatus] = useState('operational')

  // Racks are the rack slots taught on the real map (Warehouse Map -> Locations); nothing is invented from the map image
  const { data: locations = [] } = useQuery({ queryKey: ['locations'], queryFn: api.locations.list })

  const { data: recommendations } = useQuery({
    queryKey: ['slotting-recommendations'],
    queryFn: api.slotting.recommendations,
  })

  const optimizeMutation = useMutation({
    mutationFn: api.slotting.optimize,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['slotting-recommendations'] })
    },
  })

  const [racks, setRacks] = useState<RackItem[]>([])

  useEffect(() => {
    setRacks(
      locations
        .filter((l) => l.kind === 'rack_slot')
        .map((l) => ({
          id: l.id,
          code: l.code,
          zone: l.label || l.map_label || 'taught on map',
          levels: 1,
          slots: 1,
          occupiedSlots: 0,
          slotScore: 0,
          assignedSkus: '—',
          maxWeight: '—',
          status: l.issue ? 'rejected by robot' : 'operational',
        })),
    )
  }, [locations])

  const resetForm = () => {
    setCode('')
    setZone('Golden Fast-Picking')
    setShelvesCount('4')
    setSlotsPerShelf('4')
    setMaxWeight('500 kg')
    setStatus('operational')
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!code) return
    const numShelves = parseInt(shelvesCount, 10) || 4
    const numSlotsPerShelf = parseInt(slotsPerShelf, 10) || 4
    const totalSlots = numShelves * numSlotsPerShelf

    const newItem: RackItem = {
      id: `r-${Date.now()}`,
      code,
      zone,
      levels: numShelves,
      slots: totalSlots,
      occupiedSlots: 0,
      slotScore: 850,
      assignedSkus: 'Unassigned',
      maxWeight: maxWeight || '500 kg',
      status,
    }
    setRacks((prev) => [...prev, newItem])
    setIsCreateOpen(false)
    resetForm()
  }

  const handleEditSave = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingItem) return
    const numShelves = parseInt(shelvesCount, 10) || editingItem.levels
    const numSlotsPerShelf = parseInt(slotsPerShelf, 10) || 4
    const totalSlots = numShelves * numSlotsPerShelf

    setRacks((prev) =>
      prev.map((r) =>
        r.id === editingItem.id
          ? {
              ...r,
              code,
              zone,
              levels: numShelves,
              slots: totalSlots,
              maxWeight,
              status,
            }
          : r
      )
    )
    setEditingItem(null)
    resetForm()
  }

  const openEditModal = (item: RackItem) => {
    setEditingItem(item)
    setCode(item.code)
    setZone(item.zone)
    setShelvesCount(String(item.levels))
    setSlotsPerShelf(String(Math.round(item.slots / item.levels) || 4))
    setMaxWeight(item.maxWeight)
    setStatus(item.status)
  }

  const handleDelete = (id: string) => {
    setRacks((prev) => prev.filter((r) => r.id !== id))
  }

  const columns: Column<RackItem>[] = [
    {
      header: 'Rack Name',
      accessorKey: 'code',
      cell: (row) => (
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded bg-action-primary/10 border border-action-primary/30 flex items-center justify-center text-cyan font-bold text-xs font-mono">
            R
          </div>
          <div>
            <span className="font-semibold text-text-primary text-xs font-mono">{row.code}</span>
            <span className="text-[10px] text-text-secondary block font-mono">{row.zone}</span>
          </div>
        </div>
      ),
    },
    {
      header: 'Shelves / Levels',
      accessorKey: 'levels',
      cell: (row) => (
        <div className="flex items-center gap-1.5 text-xs font-mono text-cyan font-semibold">
          <Layers className="h-4 w-4 text-cyan" />
          <span>{row.levels} Shelves</span>
        </div>
      ),
    },
    {
      header: 'Capacity & Slots',
      accessorKey: 'slots',
      cell: (row) => {
        const pct = Math.round((row.occupiedSlots / row.slots) * 100)
        return (
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-text-secondary">{row.occupiedSlots} / {row.slots} Slots</span>
              <span className="text-cyan font-bold">{pct}%</span>
            </div>
            <div className="w-24 h-1.5 rounded-full bg-bg-secondary overflow-hidden border border-border-primary">
              <div
                className={`h-full rounded-full ${pct > 85 ? 'bg-error' : pct > 60 ? 'bg-warning' : 'bg-success'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      },
    },
    {
      header: 'Slotting Heat Score',
      accessorKey: 'slotScore',
      cell: (row) => (
        <div className="font-mono text-xs font-semibold text-cyan flex items-center gap-1">
          <Zap className="h-3 w-3 text-warning" />
          {row.slotScore} pts
        </div>
      ),
    },
    {
      header: 'Assigned SKUs',
      accessorKey: 'assignedSkus',
      cell: (row) => (
        <span className="text-xs font-mono text-text-secondary truncate max-w-[140px] block">
          {row.assignedSkus}
        </span>
      ),
    },
    {
      header: 'Actions',
      accessorKey: 'id',
      cell: (row) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => openEditModal(row)}
            className="p-1 rounded text-text-secondary hover:text-cyan hover:bg-bg-hover transition-colors"
            title="Configure Shelves & Rack Name"
          >
            <Edit3 className="h-4 w-4" />
          </button>
          <button
            onClick={() => handleDelete(row.id)}
            className="p-1 rounded text-text-secondary hover:text-error hover:bg-bg-hover transition-colors"
            title="Delete Rack"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ]

  const numShelvesInput = parseInt(shelvesCount, 10) || 4
  const numSlotsPerShelfInput = parseInt(slotsPerShelf, 10) || 4
  const calculatedSlots = numShelvesInput * numSlotsPerShelfInput

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-page-title">Racks & Shelves Management</h1>
          <p className="text-xs text-text-secondary">Adaptable storage rack layouts dynamically synced with SLAM Map</p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            icon={<RefreshCw className={`h-4 w-4 ${optimizeMutation.isPending ? 'animate-spin' : ''}`} />}
            onClick={() => optimizeMutation.mutate()}
            disabled={optimizeMutation.isPending}
          >
            {optimizeMutation.isPending ? 'Re-Slotting...' : 'Run SLAM Slotting Engine'}
          </Button>
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setIsCreateOpen(true)}>
            Add Storage Rack
          </Button>
        </div>
      </div>

      {/* Real-time Map Adaptive Banner */}
      <Card className="p-4 border border-cyan/30 bg-cyan/5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan/10 border border-cyan/30 text-cyan">
            <Map className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-text-primary font-mono">RACK SLOTS TAUGHT ON THE ROBOT'S MAP</h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-success/10 text-success border border-success/30 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> {racks.length} taught location{racks.length === 1 ? '' : 's'}
              </span>
            </div>
            <p className="text-[11px] text-text-secondary mt-0.5">
              Each row is a <strong>rack_slot</strong> location taught on the Warehouse Map: the places the robot can navigate to. Add or move them there.
            </p>
          </div>
        </div>
        <Link to="/warehouse-map">
          <Button variant="ghost" className="text-xs text-cyan">
            View SLAM Map <ExternalLink className="h-3.5 w-3.5 ml-1" />
          </Button>
        </Link>
      </Card>

      {/* Recommended Actions */}
      {recommendations && recommendations.length > 0 && (
        <Card className="p-4 border-warning/30 bg-warning/5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Boxes className="h-5 w-5 text-warning" />
              <div>
                <h4 className="text-xs font-bold text-text-primary font-mono">Optimized Slotting Recommendation Available</h4>
                <p className="text-[11px] text-text-secondary font-mono">
                  Product {recommendations[0].product_id} recommended for target slot {recommendations[0].slot_id} ({recommendations[0].reason})
                </p>
              </div>
            </div>
            <Link to="/recommendations">
              <Button variant="outline" className="text-xs border-warning text-warning hover:bg-warning/10">
                Apply Slotting Moves
              </Button>
            </Link>
          </div>
        </Card>
      )}

      {/* Racks Table */}
      <DataTable data={racks as unknown as Record<string, unknown>[]} columns={columns as unknown as Column<Record<string, unknown>>[]} />

      {/* Create Modal */}
      <Modal isOpen={isCreateOpen} onClose={() => { setIsCreateOpen(false); resetForm(); }} title="Configure Rack & Shelves">
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="p-3 rounded-lg bg-bg-secondary border border-cyan/30 text-xs flex items-center justify-between">
            <span className="text-text-secondary font-mono">Rack slots taught on the map:</span>
            <span className="font-mono text-cyan font-bold">{racks.length}</span>
          </div>

          <Input
            label="Rack Name / Code"
            placeholder="e.g. RACK-07"
            value={code}
            onChange={setCode}
            required
          />

          <Select
            label="Target Warehouse Zone"
            options={[
              { label: 'Golden Fast-Picking Zone', value: 'Golden Fast-Picking' },
              { label: 'Cold Storage Zone B (-18°C)', value: 'Cold Storage B' },
              { label: 'Reserve Bulk Zone C', value: 'Reserve Bulk C' },
              { label: 'Hazardous Materials Cage', value: 'Hazardous Cage' },
            ]}
            value={zone}
            onChange={setZone}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Number of Shelves (Levels)"
              type="number"
              min="1"
              max="10"
              value={shelvesCount}
              onChange={setShelvesCount}
              required
            />
            <Input
              label="Slots per Shelf"
              type="number"
              min="1"
              max="20"
              value={slotsPerShelf}
              onChange={setSlotsPerShelf}
              required
            />
          </div>

          <div className="p-3 rounded-lg bg-bg-surface border border-border-primary space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-text-secondary">Calculated Storage Capacity:</span>
              <span className="text-cyan font-bold">{calculatedSlots} Total Slots</span>
            </div>
            <p className="text-[10px] text-text-secondary">
              ({numShelvesInput} Shelves × {numSlotsPerShelfInput} Slots per shelf)
            </p>
          </div>

          <Input
            label="Max Weight Capacity per Shelf"
            placeholder="e.g. 500 kg"
            value={maxWeight}
            onChange={setMaxWeight}
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => { setIsCreateOpen(false); resetForm(); }} type="button">
              Cancel
            </Button>
            <Button type="submit">Create Storage Rack</Button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={!!editingItem} onClose={() => { setEditingItem(null); resetForm(); }} title={`Configure Shelves - ${editingItem?.code}`}>
        <form onSubmit={handleEditSave} className="space-y-4">
          <Input
            label="Rack Name / Code"
            value={code}
            onChange={setCode}
            required
          />

          <Select
            label="Target Warehouse Zone"
            options={[
              { label: 'Golden Fast-Picking Zone', value: 'Golden Fast-Picking' },
              { label: 'Cold Storage Zone B (-18°C)', value: 'Cold Storage B' },
              { label: 'Reserve Bulk Zone C', value: 'Reserve Bulk C' },
              { label: 'Hazardous Materials Cage', value: 'Hazardous Cage' },
            ]}
            value={zone}
            onChange={setZone}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Number of Shelves (Levels)"
              type="number"
              min="1"
              max="10"
              value={shelvesCount}
              onChange={setShelvesCount}
              required
            />
            <Input
              label="Slots per Shelf"
              type="number"
              min="1"
              max="20"
              value={slotsPerShelf}
              onChange={setSlotsPerShelf}
              required
            />
          </div>

          <div className="p-3 rounded-lg bg-bg-surface border border-border-primary space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-text-secondary">Calculated Storage Capacity:</span>
              <span className="text-cyan font-bold">{calculatedSlots} Total Slots</span>
            </div>
            <p className="text-[10px] text-text-secondary">
              ({numShelvesInput} Shelves × {numSlotsPerShelfInput} Slots per shelf)
            </p>
          </div>

          <Input
            label="Max Weight Capacity per Shelf"
            value={maxWeight}
            onChange={setMaxWeight}
          />

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => { setEditingItem(null); resetForm(); }} type="button">
              Cancel
            </Button>
            <Button type="submit">Save Rack Configuration</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
