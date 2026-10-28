import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { Card, DataTable, StatusBadge, PageHeader, LoadingSpinner, ErrorState, Button, toast, type Column } from '../../components/ui'
import type { User } from '../../types'

type Row = User & Record<string, unknown>

export function UsersPage() {
  const queryClient = useQueryClient()
  const { data: users, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['admin-users'],
    queryFn: api.users.list,
  })

  const toggleStatus = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.users.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('User status updated')
    },
    onError: (err: Error) => toast.error(`Update failed: ${err.message}`),
  })

  const columns: Column<Row>[] = [
    {
      header: 'Name',
      accessorKey: 'full_name',
      sortable: true,
      cell: (r) => <span className="font-semibold text-text-primary">{r.full_name}</span>,
    },
    {
      header: 'Email',
      accessorKey: 'email',
      sortable: true,
      cell: (r) => <span className="font-mono text-xs text-text-secondary">{r.email}</span>,
    },
    {
      header: 'Role',
      cell: (r) => <StatusBadge status={r.role} />,
    },
    {
      header: 'Account Status',
      cell: (r) => <StatusBadge status={r.is_active ? 'active' : 'offline'} />,
    },
    {
      header: 'Actions',
      cell: (r) => (
        <Button
          variant="outline"
          className="min-h-8 px-2.5 py-1 text-xs"
          loading={toggleStatus.isPending}
          onClick={() => toggleStatus.mutate({ id: r.id, is_active: !r.is_active })}
        >
          {r.is_active ? 'Deactivate' : 'Activate'}
        </Button>
      ),
    },
  ]

  if (isLoading) return <LoadingSpinner label="Loading users" />
  if (isError) return <ErrorState title="Could not load platform users" error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-6">
      <PageHeader
        title="User Management"
        description="Live view of platform accounts and role permissions across your organization."
      />
      <Card>
        <DataTable
          caption="Users"
          columns={columns}
          data={(users ?? []) as Row[]}
          emptyTitle="No registered users found"
        />
      </Card>
    </div>
  )
}
