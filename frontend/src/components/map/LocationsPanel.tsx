import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MapPin, Trash2, Crosshair } from 'lucide-react'
import { api } from '../../api/client'
import { Button, Input, Select } from '../ui'
import type { MapLocation } from '../../types'
import type { PickedPose } from './LiveMap'

const KINDS = [
  { value: 'rack_slot', label: 'Rack slot (where stock is stored)' },
  { value: 'receiving', label: 'Receiving (where crates arrive)' },
  { value: 'shipping', label: 'Shipping (where orders are delivered)' },
  { value: 'home', label: 'Home / dock' },
  { value: 'charging', label: 'Charging' },
  { value: 'waypoint', label: 'Waypoint' },
]

interface Props {
  locations: MapLocation[]
  pending: PickedPose | null
  onClear: () => void
}

/** Teach named places on the real map: press-drag on the map for position + heading, name it, save. The robot refuses bad spots. */
export function LocationsPanel({ locations, pending, onClear }: Props) {
  const qc = useQueryClient()
  const [kind, setKind] = useState('rack_slot')
  const [code, setCode] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['locations'] })

  const create = useMutation({
    mutationFn: api.locations.create,
    onSuccess: () => { refresh(); setCode(''); onClear() },
  })
  const remove = useMutation({ mutationFn: api.locations.remove, onSuccess: refresh })
  const pose = useMutation({
    mutationFn: (p: PickedPose) => api.robotCommunication.initialPose(p.x, p.y, (p.yaw * 180) / Math.PI),
  })

  const save = (e: React.FormEvent) => {
    e.preventDefault()
    if (!pending || !code.trim()) return
    create.mutate({ code: code.trim(), kind, x: pending.x, y: pending.y, yaw: pending.yaw })
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
        <MapPin className="h-4 w-4 text-cyan" /> Locations on this map
      </h3>

      <form onSubmit={save} className="space-y-3 p-3 rounded-lg bg-bg-secondary border border-border-primary">
        <p className="text-xs text-text-secondary">
          {pending
            ? <>Picked <span className="font-mono text-cyan">x {pending.x.toFixed(2)} m, y {pending.y.toFixed(2)} m, heading {((pending.yaw * 180) / Math.PI).toFixed(0)}°</span></>
            : 'Press on the map where the spot is and drag toward the way the robot should face when it gets there.'}
        </p>
        <Select label="Kind" value={kind} onChange={setKind} options={KINDS} />
        <Input label="Code (used by tasks)" value={code} onChange={setCode} placeholder="e.g. RACK-1, SHIP-11, HOME" />
        <div className="flex gap-2">
          <Button type="submit" disabled={!pending || !code.trim() || create.isPending}>{create.isPending ? 'Saving…' : 'Save location'}</Button>
          <Button
            type="button"
            variant="outline"
            disabled={!pending || pose.isPending}
            onClick={() => pending && pose.mutate(pending)}
            title="Tell the robot it is standing at the picked spot, facing the picked heading"
          >
            <Crosshair className="h-3.5 w-3.5 mr-1" /> Robot is here
          </Button>
        </div>
        {create.isError && <p role="alert" className="text-xs text-error font-mono">{(create.error as Error).message}</p>}
        {pose.isError && <p role="alert" className="text-xs text-error font-mono">{(pose.error as Error).message}</p>}
        {pose.isSuccess && <p className="text-xs text-success font-mono">Initial pose sent: the robot will localize there.</p>}
      </form>

      {locations.length === 0 ? (
        <p className="text-xs text-text-secondary">No locations yet. Orders and shipments wait until a rack slot, a receiving point and a shipping point are taught.</p>
      ) : (
        <ul className="space-y-2">
          {locations.map((l) => (
            <li key={l.id} className="p-2.5 rounded-lg bg-bg-secondary border border-border-primary text-xs">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <span className="font-mono font-bold text-text-primary">{l.code}</span>
                  <span className="ml-2 text-text-secondary">{l.kind}</span>
                  <div className="font-mono text-[11px] text-cyan">x {l.x.toFixed(2)} · y {l.y.toFixed(2)} · {((l.yaw * 180) / Math.PI).toFixed(0)}°</div>
                </div>
                <button
                  aria-label={`Delete ${l.code}`}
                  className="p-1.5 text-text-secondary hover:text-error cursor-pointer"
                  onClick={() => remove.mutate(l.code)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {l.issue && <p className="mt-1 text-[11px] text-error font-mono">Robot rejected it: {l.issue}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
