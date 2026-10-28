import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { useAuthStore } from '../../stores/authStore'
import { Button, Input } from '../../components/ui'
import logoSrc from '../../assets/logo.png'

// Seeded development accounts (see backend/app/main.py auto-seed). Shown only in dev builds.
const demoAccounts = [
  { email: 'admin@arms.io', password: 'admin12345', role: 'Admin' },
  { email: 'operator@arms.io', password: 'operator123', role: 'Operator' },
  { email: 'customer@arms.io', password: 'customer123', role: 'Customer' },
]

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { login, isLoading } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email.trim(), password)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-bg-primary p-4">
      <Link
        to="/"
        className="absolute left-4 top-4 flex min-h-10 items-center gap-2 rounded-[var(--radius-neu-sm)] px-3 text-sm font-medium text-text-secondary hover:text-text-primary sm:left-6 sm:top-6"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to home
      </Link>

      <motion.main
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <div className="mb-8 text-center">
          <div className="neu-float mx-auto mb-4 flex h-20 w-20 items-center justify-center p-3">
            <img src={logoSrc} alt="" className="h-full w-full object-contain" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">ARMS Console</h1>
          <p className="mt-1.5 text-sm text-text-secondary">Autonomous Robotic Management System</p>
        </div>

        <div className="neu-float space-y-5 p-6 sm:p-8">
          {error && (
            <div role="alert" className="neu-inset flex items-center gap-2 px-4 py-3 text-sm text-error">
              <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate={false}>
            <Input label="Email address" type="email" autoComplete="username" value={email} onChange={setEmail} placeholder="you@company.com" required />
            <Input label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} placeholder="Enter your password" required />

            <Button type="submit" loading={isLoading} className="w-full py-3">
              {isLoading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="pt-2">
            <p className="t-caption mb-2.5 text-center">Development accounts · click to fill</p>
            <div className="grid grid-cols-3 gap-3">
              {demoAccounts.map((account) => (
                <button
                  key={account.role}
                  type="button"
                  onClick={() => {
                    setEmail(account.email)
                    setPassword(account.password)
                  }}
                  className="neu-pressable min-h-10 cursor-pointer rounded-[var(--radius-neu-sm)] px-2 text-xs font-semibold text-text-secondary hover:text-text-primary"
                >
                  {account.role}
                </button>
              ))}
            </div>
          </div>
        </div>
      </motion.main>
    </div>
  )
}
