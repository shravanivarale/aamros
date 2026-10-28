import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bot, Package, ShoppingCart, Layers, Activity, Sparkles, ArrowRight } from 'lucide-react'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { MetricCard, Skeleton, StatusBadge, DataTable, Card, PageHeader, ErrorState, Notice, type Column } from '../../components/ui'
import type { Robot } from '../../types'
import { AssistantPanel } from './AssistantPanel'

export function DashboardPage() {
  const role = useAuthStore((s) => s.user?.role)
  const isStaff = role === 'administrator' || role === 'warehouse_operator'
  const { isConnected } = useWebSocket()

  const robots = useQuery({ queryKey: ['robots'], queryFn: api.robots.list, enabled: isStaff })
  const orders = useQuery({ queryKey: ['orders'], queryFn: api.orders.list })
  const shipments = useQuery({ queryKey: ['shipments'], queryFn: api.shipments.list, enabled: isStaff })
  const products = useQuery({ queryKey: ['products'], queryFn: api.products.list })
  const recommendations = useQuery({ queryKey: ['slotting-recommendations'], queryFn: api.slotting.recommendations, enabled: isStaff })

  const robotList = robots.data ?? []
  const activeRobots = robotList.filter((r) => r.status === 'busy' || r.status === 'working').length
  const pendingOrders = (orders.data ?? []).filter((o) => ['pending', 'processing', 'retrieving'].includes(o.status)).length
  const activeShipments = (shipments.data ?? []).filter((s) => ['registered', 'queued', 'processing'].includes(s.status)).length

  const robotColumns: Column<Robot & Record<string, unknown>>[] = [
    {
      header: 'Robot',
      accessorKey: 'name',
      sortable: true,
      cell: (row) => (
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-action-primary" aria-hidden="true" />
          <span className="font-semibold text-text-primary">{row.name}</span>
        </div>
      ),
    },
    { header: 'Serial', accessorKey: 'serial_number', cell: (row) => <span className="font-mono text-xs text-text-secondary">{row.serial_number}</span> },
    {
      header: 'Battery',
      sortable: true,
      sortValue: (row) => Number(row.battery_level),
      cell: (row) => <span className="t-numeric text-xs text-text-primary">{Number(row.battery_level).toFixed(0)}%</span>,
    },
    { header: 'Status', cell: (row) => <StatusBadge status={row.status} /> },
  ]

  const loading = orders.isLoading || products.isLoading || (isStaff && (robots.isLoading || shipments.isLoading))

  return (
    <div className="space-y-6">
      <PageHeader title="Operational Command Center" description="Live view of your fleet, orders, inbound shipments and catalog." />

      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4">
          {isStaff && <MetricCard label="Active Robots" value={`${activeRobots} / ${robotList.length}`} icon={<Bot className="h-5 w-5" />} accent="cyan" />}
          <MetricCard label="Open Orders" value={pendingOrders} icon={<ShoppingCart className="h-5 w-5" />} accent="amber" />
          {isStaff && <MetricCard label="Inbound Shipments" value={activeShipments} icon={<Package className="h-5 w-5" />} accent="electric" />}
          <MetricCard label="Catalog Products" value={products.data?.length ?? 0} icon={<Layers className="h-5 w-5" />} accent="green" />
        </div>
      )}

      {(orders.isError || products.isError || robots.isError || shipments.isError) && (
        <Notice tone="warning" title="Some figures could not be loaded">
          Counts above may be incomplete. Check your connection or permissions and refresh.
        </Notice>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <AssistantPanel />
        <Card className="lg:col-span-1">
          <h2 className="t-section-title mb-2">Start with a question</h2>
          <p className="text-sm leading-6 text-text-secondary">You do not need to know the menu structure. Ask for a status, a list, or a page and the assistant will use the access you already have.</p>
          <div className="mt-5 space-y-3 text-xs text-text-secondary">
            <p><span className="font-semibold text-text-primary">Check:</span> “What is happening with my orders?”</p>
            <p><span className="font-semibold text-text-primary">Find:</span> “Show products in the catalog”</p>
            <p><span className="font-semibold text-text-primary">Open:</span> “Take me to robot fleet”</p>
          </div>
        </Card>
      </div>

      {isStaff && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <div className="mb-4 flex items-center justify-between gap-2">
              <h2 className="t-section-title flex items-center gap-2">
                <Bot className="h-4 w-4 text-action-primary" aria-hidden="true" /> Robot fleet
              </h2>
              <Link to="/robots" className="inline-flex items-center gap-1 text-xs font-semibold text-action-primary hover:underline">
                Manage fleet <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
            {robots.isError ? (
              <ErrorState title="Could not load robots" error={robots.error} onRetry={() => robots.refetch()} />
            ) : (
              <DataTable
                caption="Robot fleet"
                columns={robotColumns}
                data={robotList as (Robot & Record<string, unknown>)[]}
                pageSize={5}
                emptyTitle="No robots registered"
                emptyDescription="Register robots on the Robot Fleet page to monitor them here."
              />
            )}
          </Card>

          <div className="space-y-6">
            <Card>
              <h2 className="t-section-title mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-action-primary" aria-hidden="true" /> Slotting
              </h2>
              {recommendations.isError ? (
                <p className="text-sm text-text-secondary">Slot recommendations are unavailable right now.</p>
              ) : (
                <>
                  <p className="t-numeric text-3xl text-text-primary">{recommendations.data?.length ?? '–'}</p>
                  <p className="mt-1 text-sm text-text-secondary">slot recommendations generated</p>
                  <Link to="/slotting/recommendations" className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-action-primary hover:underline">
                    Review recommendations <ArrowRight className="h-3 w-3" aria-hidden="true" />
                  </Link>
                </>
              )}
            </Card>

            <Card>
              <h2 className="t-section-title mb-4 flex items-center gap-2">
                <Activity className="h-4 w-4 text-action-primary" aria-hidden="true" /> System status
              </h2>
              <dl className="space-y-3 text-sm">
                <StatusRow label="API" ok={!orders.isError && !products.isError} okText="Reachable" badText="Errors" />
                <StatusRow label="Telemetry socket" ok={isConnected} okText="Connected" badText="Reconnecting" />
              </dl>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusRow({ label, ok, okText, badText }: { label: string; ok: boolean; okText: string; badText: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-text-secondary">{label}</dt>
      <dd className={`flex items-center gap-2 font-semibold ${ok ? 'text-success' : 'text-amber'}`}>
        <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
        {ok ? okText : badText}
      </dd>
    </div>
  )
}
