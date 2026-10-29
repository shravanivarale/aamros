import { hasBattery } from '../../utils/format'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Battery, DollarSign, ShoppingCart } from 'lucide-react'
import { api } from '../../api/client'
import { Card, MetricCard, PageHeader, LoadingSpinner, ErrorState, EmptyState } from '../../components/ui'

function BarList({ items, unit = '' }: { items: { label: string; value: number }[]; unit?: string }) {
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
            <span className="truncate font-medium capitalize text-text-primary">{item.label}</span>
            <span className="t-numeric text-text-secondary">
              {item.value}
              {unit}
            </span>
          </div>
          <div className="neu-inset h-3 overflow-hidden !rounded-full" role="presentation">
            <div className="h-full rounded-full bg-action-primary" style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function AnalyticsDashboardPage() {
  const orders = useQuery({ queryKey: ['orders'], queryFn: api.orders.list })
  const robots = useQuery({ queryKey: ['robots'], queryFn: api.robots.list })

  if (orders.isLoading || robots.isLoading) return <LoadingSpinner label="Loading analytics" />
  if (orders.isError) return <ErrorState title="Could not load orders" error={orders.error} onRetry={() => orders.refetch()} />

  const orderList = orders.data ?? []
  const robotList = robots.data ?? []
  const totalValue = orderList.reduce((sum, o) => sum + Number(o.total_amount || 0), 0)
  const measured = robotList.filter((r) => hasBattery(Number(r.battery_level)))   // only robots that actually report a battery
  const avgBattery = measured.length ? measured.reduce((s, r) => s + Number(r.battery_level), 0) / measured.length : null

  const byStatus = new Map<string, number>()
  for (const o of orderList) byStatus.set(o.status, (byStatus.get(o.status) ?? 0) + 1)

  return (
    <div className="space-y-6">
      <PageHeader title="Operational Analytics" description="Figures computed from live order and robot data." />

      <div className="grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4">
        <MetricCard label="Total orders" value={orderList.length} icon={<ShoppingCart className="h-5 w-5" />} accent="cyan" />
        <MetricCard label="Order value" value={`$${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} icon={<DollarSign className="h-5 w-5" />} accent="amber" />
        <MetricCard label="Robots" value={robotList.length} icon={<BarChart3 className="h-5 w-5" />} accent="electric" />
        <MetricCard label="Avg battery" value={avgBattery == null ? '—' : `${avgBattery.toFixed(0)}%`} icon={<Battery className="h-5 w-5" />} accent="green" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="t-section-title mb-5">Orders by status</h2>
          {byStatus.size === 0 ? <EmptyState title="No orders yet" /> : <BarList items={[...byStatus].map(([label, value]) => ({ label, value }))} />}
        </Card>
        <Card>
          <h2 className="t-section-title mb-5">Robot battery levels</h2>
          {robotList.length === 0 ? (
            <EmptyState title="No robots" description={robots.isError ? 'Robot data could not be loaded.' : 'Register robots to see battery levels.'} />
          ) : (
            measured.length ? (
            <BarList items={measured.map((r) => ({ label: r.name, value: Math.round(Number(r.battery_level)) }))} unit="%" />
          ) : (
            <EmptyState title="Battery not measured" description="This robot has no battery sensor connected, so no level is shown." />
          )
          )}
        </Card>
      </div>
    </div>
  )
}
