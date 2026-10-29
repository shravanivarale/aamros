import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Server, Plus, Trash2, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { api } from '../../api/client'
import { Button, Card, Input } from '../ui'
import type { BridgeEndpoint, BridgeProbe } from '../../types'

const STATE_STYLE: Record<BridgeEndpoint['state'], string> = {
  online: 'bg-success/10 text-success border-success/30',
  offline: 'bg-error/10 text-error border-error/30',
  connecting: 'bg-warning/10 text-warning border-warning/30',
  disabled: 'bg-bg-secondary text-text-secondary border-border-primary',
}

/** Admin: the robot PCs (wms_bridge) the platform talks to. Add an IP here and its robots appear within seconds. */
export function BridgesPanel() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('8005')
  const [secure, setSecure] = useState(false)
  const [token, setToken] = useState('')
  const [probe, setProbe] = useState<BridgeProbe | null>(null)

  const bridges = useQuery({ queryKey: ['bridges'], queryFn: api.bridges.list, refetchInterval: 4000 })
  const refresh = () => qc.invalidateQueries({ queryKey: ['bridges'] })
  const portNum = parseInt(port, 10)
  const valid = host.trim().length > 0 && portNum > 0 && portNum < 65536

  const test = useMutation({ mutationFn: () => api.bridges.test(host.trim(), portNum, secure ? 'https' : 'http', token.trim()), onSuccess: setProbe })
  const create = useMutation({
    mutationFn: () => api.bridges.create({ name: name.trim() || host.trim(), host: host.trim(), port: portNum, scheme: secure ? 'https' : 'http', token: token.trim() || undefined }),
    onSuccess: () => { refresh(); setName(''); setHost(''); setPort('8005'); setSecure(false); setToken(''); setProbe(null) },
  })
  const toggle = useMutation({ mutationFn: (b: BridgeEndpoint) => api.bridges.update(b.id, { enabled: !b.enabled }), onSuccess: refresh })
  const remove = useMutation({ mutationFn: (id: string) => api.bridges.remove(id), onSuccess: refresh })

  return (
    <Card className="md:col-span-2">
      <h2 className="t-section-title mb-1 flex items-center gap-2">
        <Server className="h-4 w-4 text-action-primary" aria-hidden="true" /> Robot bridges
      </h2>
      <p className="mb-4 text-xs text-text-secondary">
        Each robot PC runs the ROS 2 <span className="font-mono">wms_bridge</span> (port 8005 by default). Add its IP address and the robots on it
        appear on the dashboards, receive tasks and show on the live map. No restart needed.
      </p>

      {bridges.isError && <p role="alert" className="mb-3 text-xs text-error font-mono">{(bridges.error as Error).message}</p>}
      {bridges.data?.length === 0 && (
        <p className="mb-3 text-sm text-text-secondary">No robot PC configured yet: nothing can move or report until you add one below.</p>
      )}

      <ul className="mb-5 space-y-2">
        {bridges.data?.map((b) => (
          <li key={b.id} className="rounded-lg border border-border-primary bg-bg-secondary p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                {b.state === 'online' ? <Wifi className="h-4 w-4 text-success" aria-hidden="true" />
                  : b.state === 'connecting' ? <Loader2 className="h-4 w-4 animate-spin text-warning" aria-hidden="true" />
                  : <WifiOff className="h-4 w-4 text-text-secondary" aria-hidden="true" />}
                <div>
                  <div className="font-semibold text-text-primary">{b.name}</div>
                  <div className="font-mono text-xs text-text-secondary">{b.scheme}://{b.host}:{b.port}{b.has_token ? ' · token set' : ''}</div>
                </div>
                <span className={`rounded border px-2 py-0.5 text-[11px] font-mono ${STATE_STYLE[b.state]}`}>{b.state}</span>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" className="text-xs py-1" disabled={toggle.isPending} onClick={() => toggle.mutate(b)}>
                  {b.enabled ? 'Disable' : 'Enable'}
                </Button>
                <button
                  aria-label={`Remove ${b.name}`}
                  className="cursor-pointer p-2 text-text-secondary hover:text-error"
                  onClick={() => { if (window.confirm(`Remove ${b.name} (${b.host}:${b.port})? Its robots will show offline.`)) remove.mutate(b.id) }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {b.state === 'offline' && b.error && <p className="mt-2 break-all font-mono text-[11px] text-error">{b.error}</p>}
            {b.state === 'online' && (
              <p className="mt-2 font-mono text-[11px] text-text-secondary">
                {b.robots.length ? b.robots.map((r) => `${r.robot_id} (${r.status.toLowerCase()}${r.localized ? ', localized' : ', not localized'})`).join(' · ') : 'no robots reported'}
                {' · '}motion {b.allow_motion ? 'ENABLED' : 'disabled'}
              </p>
            )}
          </li>
        ))}
      </ul>

      <form
        onSubmit={(e) => { e.preventDefault(); if (valid) create.mutate() }}
        className="space-y-3 rounded-lg border border-border-primary p-3"
      >
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Plus className="h-4 w-4" /> Add a robot PC</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input label="Name" value={name} onChange={setName} placeholder="e.g. Warehouse floor 1" />
          <Input label="IP address / hostname" value={host} onChange={(v) => { setHost(v); setProbe(null) }} placeholder="e.g. 10.113.140.148" required />
          <Input label="Port" type="number" value={port} onChange={(v) => { setPort(v); setProbe(null) }} required />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input label="API token (if the bridge has one)" type="password" value={token} onChange={(v) => { setToken(v); setProbe(null) }} placeholder="same as api_token on the robot PC" />
          <label className="flex items-end gap-2 pb-2 text-sm text-text-primary">
            <input type="checkbox" checked={secure} onChange={(e) => { setSecure(e.target.checked); setPort(e.target.checked ? '443' : '8005'); setProbe(null) }} />
            Secure (https), e.g. a Cloudflare tunnel
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" disabled={!valid || test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? 'Testing…' : 'Test connection'}
          </Button>
          <Button type="submit" disabled={!valid || create.isPending}>{create.isPending ? 'Adding…' : 'Add'}</Button>
        </div>
        {test.isError && <p role="alert" className="text-xs text-error font-mono">{(test.error as Error).message}</p>}
        {probe && (
          <p role="status" className={`text-xs font-mono ${probe.reachable ? 'text-success' : 'text-error'}`}>
            {probe.reachable
              ? `Reachable. Robots: ${probe.robots?.map((r) => r.robot_id).join(', ') || 'none'} · motion ${probe.allow_motion ? 'ENABLED' : 'disabled'}${probe.localized ? ' · localized' : ''}`
              : `Not reachable: ${probe.error}. You can still add it; it will connect when the robot PC is up.`}
          </p>
        )}
        {create.isError && <p role="alert" className="text-xs text-error font-mono">{(create.error as Error).message}</p>}
      </form>
    </Card>
  )
}
