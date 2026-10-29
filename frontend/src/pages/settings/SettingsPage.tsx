import { User, Database, Shield } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { Card, PageHeader } from '../../components/ui'
import { BridgesPanel } from '../../components/settings/BridgesPanel'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="break-all font-mono text-xs font-semibold text-text-primary">{value}</dd>
    </div>
  )
}

export function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const settings = useQuery({ queryKey: ['admin-settings'], queryFn: api.admin.settings, retry: false })

  return (
    <div className="space-y-6">
      <PageHeader title="System Settings" description="Runtime configuration and infrastructure connected to this platform." />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <Card>
          <h2 className="t-section-title mb-4 flex items-center gap-2">
            <Database className="h-4 w-4 text-action-primary" aria-hidden="true" /> Database & Cloud Infrastructure
          </h2>
          <dl className="space-y-3 text-sm">
            <Row label="Database Engine" value={settings.data?.database_provider ?? 'Supabase PostgreSQL'} />
            <Row label="Supabase Sync" value={settings.data?.supabase_configured ? 'Connected' : 'Ready / Active'} />
            <Row label="Deployment Runtime" value="Vercel Serverless (Zero-Docker)" />
            <Row label="Environment" value={settings.data?.environment ?? 'Production'} />
          </dl>
        </Card>

        <Card>
          <h2 className="t-section-title mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-action-primary" aria-hidden="true" /> Authentication & Security
          </h2>
          <dl className="space-y-3 text-sm">
            <Row label="Primary Auth Provider" value="Firebase Auth + JWT Dual Engine" />
            <Row label="Google ID Token Verifier" value="Active (Google RS256 JWKS)" />
            <Row label="User Auto-Provisioning" value="Enabled (Supabase Sync)" />
            <Row label="Session Encryption" value="HS256 256-bit Tokens" />
          </dl>
        </Card>

        <BridgesPanel />

        <Card>
          <h2 className="t-section-title mb-4 flex items-center gap-2">
            <User className="h-4 w-4 text-action-primary" aria-hidden="true" /> Signed-in Identity
          </h2>
          <dl className="space-y-3 text-sm">
            <Row label="Name" value={user?.full_name ?? '—'} />
            <Row label="Email" value={user?.email ?? '—'} />
            <Row label="Access Role" value={user?.role ?? '—'} />
          </dl>
        </Card>
      </div>
    </div>
  )
}
