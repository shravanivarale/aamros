import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, ArrowRightLeft, Bot } from 'lucide-react'
import { api } from '../../api/client'
import { Card, DataTable, PageHeader, LoadingSpinner, ErrorState, StatusBadge, type Column } from '../../components/ui'

interface MovementRow extends Record<string, unknown> {
  id: string
  sku: string
  product_name: string
  movement_type: string
  quantity: number
  source_location: string
  destination_location: string
  robot_name: string
  timestamp: string
  status: string
}

export function StockMovementsPage() {
  const { data: movements, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['stock-movements'],
    queryFn: api.stockMovements.list,
  })

  const columns: Column<MovementRow>[] = [
    {
      header: 'Movement',
      accessorKey: 'movement_type',
      cell: (r) => {
        const type = String(r.movement_type).toUpperCase()
        const Icon = type === 'PUTAWAY' ? ArrowDownRight : type === 'PICK' ? ArrowUpRight : ArrowRightLeft
        return (
          <div className="flex items-center gap-2">
            <span className="neu-inset flex h-7 w-7 items-center justify-center rounded-md text-action-primary">
              <Icon className="h-4 w-4" />
            </span>
            <span className="font-semibold text-xs text-text-primary">{type}</span>
          </div>
        )
      },
    },
    {
      header: 'Product',
      accessorKey: 'product_name',
      cell: (r) => (
        <div>
          <div className="font-medium text-xs text-text-primary">{r.product_name}</div>
          <span className="font-mono text-[10px] text-cyan">{r.sku}</span>
        </div>
      ),
    },
    {
      header: 'Qty',
      accessorKey: 'quantity',
      cell: (r) => <span className="font-mono text-xs font-semibold text-text-primary">{r.quantity}</span>,
    },
    {
      header: 'Transfer Route',
      cell: (r) => (
        <div className="font-mono text-xs text-text-secondary">
          <span className="text-text-primary">{r.source_location}</span> &rarr; <span className="text-action-primary">{r.destination_location}</span>
        </div>
      ),
    },
    {
      header: 'Robot',
      cell: (r) => (
        <div className="flex items-center gap-1.5 text-xs text-text-primary">
          <Bot className="h-3.5 w-3.5 text-action-primary" />
          <span>{r.robot_name}</span>
        </div>
      ),
    },
    {
      header: 'Timestamp',
      cell: (r) => <span className="font-mono text-xs text-text-secondary">{new Date(r.timestamp).toLocaleTimeString()}</span>,
    },
    {
      header: 'Status',
      cell: (r) => <StatusBadge status={r.status} />,
    },
  ]

  if (isLoading) return <LoadingSpinner label="Loading stock movements" />
  if (isError) return <ErrorState title="Could not load stock movements" error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-6">
      <PageHeader
        title="Stock Movements"
        description="Audit trail of autonomous warehouse putaways, relocations and picking transfers."
      />
      <Card>
        <DataTable
          caption="Stock Movements"
          columns={columns}
          data={(movements ?? []) as MovementRow[]}
          emptyTitle="No movements recorded yet"
        />
      </Card>
    </div>
  )
}
