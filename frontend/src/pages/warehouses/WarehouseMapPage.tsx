import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Map, Upload, CheckCircle2, FileCode, Image as ImageIcon, X } from 'lucide-react'
import { api } from '../../api/client'
import { Card, LoadingSpinner, Button, Modal, Input } from '../../components/ui'
import { LiveMap, type PickedPose } from '../../components/map/LiveMap'
import { LocationsPanel } from '../../components/map/LocationsPanel'
import { useLiveStore } from '../../stores/liveStore'

export function WarehouseMapPage() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [resolution, setResolution] = useState('0.05')
  const [originX, setOriginX] = useState('0.0')
  const [originY, setOriginY] = useState('0.0')
  const [width, setWidth] = useState('800')
  const [height, setHeight] = useState('600')
  const [pgmData, setPgmData] = useState<string>('')
  const [selectedFileName, setSelectedFileName] = useState<string>('')
  const [isDragging, setIsDragging] = useState(false)

  const [pending, setPending] = useState<PickedPose | null>(null)
  const { data: locations = [] } = useQuery({ queryKey: ['locations'], queryFn: api.locations.list })
  const liveRobots = useLiveStore((st) => st.robots)
  const anyLocalized = Object.values(liveRobots).some((r) => r.localized)
  const robotsOnline = Object.values(liveRobots).filter((r) => r.status && r.status !== 'offline').length

  const { data: mapData, isLoading } = useQuery({
    queryKey: ['map', 'current'],
    queryFn: api.map.getCurrent
  })

  const uploadMutation = useMutation({
    mutationFn: api.map.upload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['map'] })
      setIsModalOpen(false)
      resetForm()
    },
  })

  const resetForm = () => {
    setLabel('')
    setResolution('0.05')
    setOriginX('0.0')
    setOriginY('0.0')
    setWidth('800')
    setHeight('600')
    setPgmData('')
    setSelectedFileName('')
    setIsDragging(false)
  }

  // Handle file reading (PGM, PNG, JPG, YAML)
  const processFile = (file: File) => {
    if (!file) return
    setSelectedFileName(file.name)
    
    // Default label from file name if empty
    if (!label) {
      const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
      setLabel(cleanName.charAt(0).toUpperCase() + cleanName.slice(1))
    }

    const reader = new FileReader()

    if (file.name.endsWith('.yaml') || file.name.endsWith('.yml')) {
      reader.onload = (e) => {
        const text = e.target?.result as string
        if (text) {
          // Parse YAML parameters (resolution, origin)
          const resMatch = text.match(/resolution:\s*([\d.]+)/)
          const origMatch = text.match(/origin:\s*\[\s*([-\d.]+)\s*,\s*([-\d.]+)/)
          if (resMatch && resMatch[1]) setResolution(resMatch[1])
          if (origMatch && origMatch[1] && origMatch[2]) {
            setOriginX(origMatch[1])
            setOriginY(origMatch[2])
          }
          setPgmData(text)
        }
      }
      reader.readAsText(file)
    } else {
      // Image or binary PGM file
      reader.onload = (e) => {
        const result = e.target?.result as string
        if (result) {
          setPgmData(result)

          // Try loading image to extract natural pixel dimensions
          const img = new Image()
          img.onload = () => {
            if (img.width) setWidth(String(img.width))
            if (img.height) setHeight(String(img.height))
          }
          img.src = result
        }
      }
      reader.readAsDataURL(file)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) processFile(file)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) processFile(file)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!label || !pgmData) return
    uploadMutation.mutate({
      label,
      pgm_data: pgmData,
      resolution: parseFloat(resolution) || 0.05,
      origin_x: parseFloat(originX) || 0.0,
      origin_y: parseFloat(originY) || 0.0,
      width_px: parseInt(width, 10) || 800,
      height_px: parseInt(height, 10) || 600,
    })
  }

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-page-title">Spatial SLAM Warehouse Map</h1>
          <p className="text-xs text-text-secondary">2D occupancy grid maps ingested from ROS2 Cartographer / SLAM</p>
        </div>
        <Button icon={<Upload className="h-4 w-4" />} onClick={() => setIsModalOpen(true)}>
          Upload PGM Map
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              <Map className="h-4 w-4 text-cyan" />
              Active map: {mapData?.label || 'none yet'}
            </h3>
            {mapData && (
              <span className="text-xs font-mono text-cyan flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5 text-success" /> Live
              </span>
            )}
          </div>

          <div className="bg-[#020617] rounded-xl border border-border-primary p-2 relative overflow-hidden">
            <LiveMap mapData={mapData} locations={locations} onPick={setPending} pending={pending} height={520} />
          </div>
          <p className="text-[11px] text-text-secondary">
            Live robots are drawn on the map in real time. Press and drag anywhere on the map to pick a position and heading, then name it in the panel.
          </p>
        </Card>

        <Card className="space-y-4">
          <h3 className="text-sm font-semibold text-text-primary">Map Metadata & Metrics</h3>
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary space-y-1">
              <span className="text-text-secondary text-[10px] uppercase font-mono block">Origin Coordinates</span>
              <span className="font-mono text-cyan">
                X: {mapData?.origin_x || 0.0}m | Y: {mapData?.origin_y || 0.0}m
              </span>
            </div>

            <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary space-y-1">
              <span className="text-text-secondary text-[10px] uppercase font-mono block">Resolution Scale</span>
              <span className="font-mono text-text-primary">
                {mapData?.resolution || 0.05} meters per pixel
              </span>
            </div>

            <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary space-y-1">
              <span className="text-text-secondary text-[10px] uppercase font-mono block">Robot link</span>
              <span className={`font-mono ${robotsOnline ? 'text-success' : 'text-text-secondary'}`}>
                {robotsOnline ? `${robotsOnline} robot(s) online${anyLocalized ? ', localized on this map' : ', not localized yet'}` : 'No robot connected'}
              </span>
            </div>

            <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary space-y-1">
              <span className="text-text-secondary text-[10px] uppercase font-mono block">Taught locations</span>
              <span className="font-mono text-text-primary">{locations.length} on this map</span>
            </div>
          </div>
        </Card>

        <Card className="lg:col-span-3">
          <LocationsPanel locations={locations} pending={pending} onClear={() => setPending(null)} />
        </Card>
      </div>

      {/* Upload Modal */}
      <Modal isOpen={isModalOpen} onClose={() => { setIsModalOpen(false); resetForm(); }} title="Upload ROS2 Occupancy Grid Map (.PGM / .PNG / .YAML)">
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Map Label / Name"
            placeholder="e.g. Facility-A-Floor-1 SLAM Model"
            value={label}
            onChange={setLabel}
            required
          />

          <div className="grid grid-cols-2 gap-3">
            <Input label="Resolution (m/px)" type="number" step="0.001" value={resolution} onChange={setResolution} required />
            <Input label="Origin X (m)" type="number" step="0.1" value={originX} onChange={setOriginX} required />
            <Input label="Width (px)" type="number" value={width} onChange={setWidth} required />
            <Input label="Height (px)" type="number" value={height} onChange={setHeight} required />
          </div>

          {/* Interactive Drag and Drop Area */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`p-6 border-2 border-dashed rounded-xl text-center cursor-pointer transition-all duration-200 ${
              isDragging
                ? 'border-cyan bg-cyan/10 scale-[1.01]'
                : selectedFileName
                ? 'border-success/50 bg-success/5'
                : 'border-border-primary hover:border-cyan hover:bg-bg-secondary/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pgm,.yaml,.yml,.png,.jpg,.jpeg,.json"
              onChange={handleFileChange}
              className="hidden"
            />

            {selectedFileName ? (
              <div className="space-y-2">
                <div className="flex items-center justify-center gap-2 text-success font-semibold text-xs">
                  {selectedFileName.endsWith('.yaml') ? <FileCode className="h-5 w-5" /> : <ImageIcon className="h-5 w-5" />}
                  <span>{selectedFileName}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedFileName('')
                      setPgmData('')
                    }}
                    className="p-1 rounded hover:bg-error/20 text-error"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <p className="text-[11px] text-text-secondary">File parsed successfully! Click Ingest Map below.</p>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className={`h-8 w-8 mx-auto ${isDragging ? 'text-cyan animate-bounce' : 'text-action-primary'}`} />
                <div>
                  <p className="text-xs font-semibold text-text-primary">
                    {isDragging ? 'Drop Map File Here...' : 'Drag & Drop .PGM / .PNG / .YAML Map File Here'}
                  </p>
                  <p className="text-[11px] text-text-secondary mt-1">Or click anywhere to browse local files</p>
                </div>
                <p className="text-[10px] text-text-secondary font-mono">
                  Supported formats: Cartographer .PGM, ROS .YAML, PNG, JPG
                </p>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => { setIsModalOpen(false); resetForm(); }} type="button">
              Cancel
            </Button>
            <Button type="submit" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? 'Ingesting Map...' : 'Ingest Map'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
