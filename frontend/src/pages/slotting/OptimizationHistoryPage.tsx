import { useQuery } from '@tanstack/react-query'
import { Sparkles, TrendingDown } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { Card, DataTable, PageHeader, LoadingSpinner, ErrorState, StatusBadge, Button, type Column } from '../../components/ui'

interface HistoryRow extends Record<string, unknown> {
  id: string
  created_at: string
  status: string
  algorithm: string
  recommendations_count: number
  travel_reduction_pct: number
  relocation_tasks: number
  runtime_ms: number
}

export function OptimizationHistoryPage() {
  const { data: runs, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['slotting-history'],
    queryFn: api.slotting.history,
  })

  const columns: Column<HistoryRow>[] = [
    {
      header: 'Run Identifier',
      accessorKey: 'id',
      sortable: true,
      cell: (r) => <span className="font-mono text-xs font-semibold text-action-primary">{r.id}</span>,
    },
    {
      header: 'Algorithm',
      accessorKey: 'algorithm',
      cell: (r) => <span className="text-xs font-medium text-text-primary">{r.algorithm}</span>,
    },
    {
      header: 'Travel Savings',
      sortable: true,
      cell: (r) => (
        <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-success">
          <TrendingDown className="h-3.5 w-3.5" />
          <span>-{r.travel_reduction_pct}%</span>
        </div>
      ),
    },
    {
      header: 'Recommendations',
      accessorKey: 'recommendations_count',
      cell: (r) => <span className="font-mono text-xs text-text-primary">{r.recommendations_count} slots</span>,
    },
    {
      header: 'Relocation Jobs',
      accessorKey: 'relocation_tasks',
      cell: (r) => <span className="font-mono text-xs text-cyan">{r.relocation_tasks} tasks</span>,
    },
    {
      header: 'Runtime',
      accessorKey: 'runtime_ms',
      cell: (r) => <span className="font-mono text-xs text-text-secondary">{r.runtime_ms} ms</span>,
    },
    {
      header: 'Date & Time',
      cell: (r) => <span className="font-mono text-xs text-text-secondary">{new Date(r.created_at).toLocaleString()}</span>,
    },
    {
      header: 'Status',
      cell: (r) => <StatusBadge status={r.status.toLowerCase()} />,
    },
  ]

  if (isLoading) return <LoadingSpinner label="Loading optimization history" />
  if (isError) return <ErrorState title="Could not load run history" error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-6">
      <PageHeader
        title="Optimization History"
        description="Historical optimizer runs, travel savings calculations and generated relocation jobs."
        actions={
          <Link to="/slotting/recommendations">
            <Button icon={<Sparkles className="h-4 w-4" />}>
              Active Recommendations
            </Button>
          </Link>
        }
      />
      <Card>
        <DataTable
          caption="Optimization Runs"
          columns={columns}
          data={(runs ?? []) as HistoryRow[]}
          emptyTitle="No optimization runs recorded"
        />
      </Card>
    </div>
  )
}
