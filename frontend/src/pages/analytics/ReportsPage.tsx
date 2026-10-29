import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { api } from '../../api/client'
import { downloadCsv } from '../../utils/csv'
import { Card, DataTable, Button, PageHeader, toast, type Column } from '../../components/ui'

interface ReportRow extends Record<string, unknown> {
  key: string
  name: string
  description: string
  records: number | null
  loading: boolean
  error: boolean
  build: () => Record<string, unknown>[]
}

export function ReportsPage() {
  const products = useQuery({ queryKey: ['products'], queryFn: api.products.list })
  const orders = useQuery({ queryKey: ['orders'], queryFn: api.orders.list })
  const robots = useQuery({ queryKey: ['robots'], queryFn: api.robots.list })
  const shipments = useQuery({ queryKey: ['shipments'], queryFn: api.shipments.list })

  const rows: ReportRow[] = [
    {
      key: 'products',
      name: 'Product catalog',
      description: 'SKU, pricing, weight and ABC/XYZ classification',
      records: products.data?.length ?? null,
      loading: products.isLoading,
      error: products.isError,
      build: () => (products.data ?? []).map((p) => ({ sku: p.sku, name: p.name, unit_price: p.unit_price, weight_kg: p.weight_kg ?? '', abc_class: p.abc_class ?? '', xyz_class: p.xyz_class ?? '' })),
    },
    {
      key: 'orders',
      name: 'Orders',
      description: 'Order numbers, status and totals',
      records: orders.data?.length ?? null,
      loading: orders.isLoading,
      error: orders.isError,
      build: () => (orders.data ?? []).map((o) => ({ order_number: o.order_number, status: o.status, total_amount: o.total_amount, line_items: o.items.length, created_at: o.created_at })),
    },
    {
      key: 'robots',
      name: 'Robot fleet',
      description: 'Robots, status and battery levels',
      records: robots.data?.length ?? null,
      loading: robots.isLoading,
      error: robots.isError,
      build: () => (robots.data ?? []).map((r) => ({ name: r.name, model: r.model, serial_number: r.serial_number, status: r.status, battery_level: r.battery_level < 0 ? null : r.battery_level, enabled: r.is_enabled })),
    },
    {
      key: 'shipments',
      name: 'Inbound shipments',
      description: 'Shipment numbers, status and item counts',
      records: shipments.data?.length ?? null,
      loading: shipments.isLoading,
      error: shipments.isError,
      build: () => (shipments.data ?? []).map((s) => ({ shipment_number: s.shipment_number, status: s.status, items: s.items.length, created_at: s.created_at })),
    },
  ]

  const exportRow = (row: ReportRow) => {
    const data = row.build()
    if (data.length === 0) {
      toast.info(`There are no ${row.name.toLowerCase()} records to export.`)
      return
    }
    downloadCsv(`arms-${row.key}-${new Date().toISOString().slice(0, 10)}.csv`, data)
    toast.success(`Exported ${data.length} ${row.name.toLowerCase()} records.`)
  }

  const columns: Column<ReportRow>[] = [
    { header: 'Dataset', accessorKey: 'name', sortable: true, cell: (r) => <span className="font-semibold text-text-primary">{r.name}</span> },
    { header: 'Contents', cell: (r) => <span className="text-xs text-text-secondary">{r.description}</span> },
    {
      header: 'Records',
      cell: (r) => <span className="t-numeric text-xs text-text-primary">{r.loading ? '…' : r.error ? 'Unavailable' : r.records}</span>,
    },
    {
      header: 'Export',
      cell: (r) => (
        <Button variant="outline" className="min-h-9 px-3 py-1 text-xs" icon={<Download className="h-3.5 w-3.5" />} disabled={r.loading || r.error} onClick={() => exportRow(r)} aria-label={`Export ${r.name} as CSV`}>
          CSV
        </Button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader title="Reports & Data Export" description="Download live operational datasets as CSV files." />
      <Card>
        <DataTable caption="Exportable datasets" columns={columns} data={rows} />
      </Card>
    </div>
  )
}
