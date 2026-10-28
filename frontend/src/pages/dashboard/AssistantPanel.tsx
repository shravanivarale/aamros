import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, Send, Sparkles, UserRound } from 'lucide-react'
import { api } from '../../api/client'
import { Button, Card, Textarea } from '../../components/ui'

type Message = { role: 'user' | 'assistant'; content: string; data?: Record<string, unknown> | null }

const starterPrompts = [
  'Give me a quick overview',
  'What orders are open?',
  'Show me the robot fleet',
  'Open inventory',
]

export function AssistantPanel() {
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Tell me what you want to check. I can summarize your workspace, find orders or products, check fleet activity, and open the right page for you.' },
  ])
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event?: FormEvent) {
    event?.preventDefault()
    const trimmed = message.trim()
    if (!trimmed || isSending) return

    const nextMessages = [...messages, { role: 'user' as const, content: trimmed }]
    setMessages(nextMessages)
    setMessage('')
    setError(null)
    setIsSending(true)
    try {
      const response = await api.assistant.chat(trimmed, nextMessages.slice(-8).map(({ role, content }) => ({ role, content })))
      setMessages([...nextMessages, { role: 'assistant', content: response.answer, data: response.data }])
      if (response.navigate_to) navigate(response.navigate_to)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'The assistant is unavailable right now.')
    } finally {
      setIsSending(false)
    }
  }

  return (
    <Card className="flex min-h-[31rem] flex-col overflow-hidden border border-action-primary/20 bg-[linear-gradient(145deg,var(--c-base),color-mix(in_srgb,var(--c-accent)_8%,var(--c-base)))] lg:col-span-2">
      <div className="flex items-start justify-between gap-4 border-b border-border-primary pb-4">
        <div>
          <p className="t-label flex items-center gap-2 uppercase text-action-primary"><Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Workspace guide</p>
          <h2 className="t-section-title mt-1">Ask ARMS</h2>
          <p className="mt-1 text-sm text-text-secondary">Use plain English to find information or open a workspace.</p>
        </div>
        <div className="neu-inset flex h-11 w-11 shrink-0 items-center justify-center text-action-primary" aria-hidden="true"><Bot className="h-5 w-5" /></div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto py-4" aria-live="polite">
        {messages.map((item, index) => (
          <div key={`${item.role}-${index}`} className={`flex gap-2.5 ${item.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {item.role === 'assistant' && <div className="neu-inset mt-1 flex h-7 w-7 shrink-0 items-center justify-center text-action-primary"><Bot className="h-3.5 w-3.5" aria-hidden="true" /></div>}
            <div className={`max-w-[85%] rounded-[var(--radius-neu-sm)] px-3.5 py-2.5 text-sm ${item.role === 'user' ? 'bg-action-primary text-[var(--c-accent-ink)]' : 'bg-bg-secondary text-text-primary shadow-[var(--neu-inset)]'}`}>
              <p>{item.content}</p>
              {item.data && <ResultDetails data={item.data} />}
            </div>
            {item.role === 'user' && <UserRound className="mt-1 h-4 w-4 shrink-0 text-text-secondary" aria-hidden="true" />}
          </div>
        ))}
        {isSending && <p className="pl-10 text-xs text-text-secondary">Checking your workspace...</p>}
      </div>

      {messages.length === 1 && <div className="flex flex-wrap gap-2 pb-3">{starterPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => setMessage(prompt)} className="neu-pressable rounded-full px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-action-primary">{prompt}</button>)}</div>}
      {error && <p role="alert" className="mb-2 text-xs text-error">{error}</p>}
      <form onSubmit={submit} className="flex items-end gap-2 border-t border-border-primary pt-3">
        <Textarea value={message} onChange={setMessage} rows={2} placeholder="For example: show me orders waiting for picking" aria-label="Ask ARMS" className="flex-1" />
        <Button type="submit" loading={isSending} disabled={!message.trim()} icon={<Send className="h-4 w-4" />} aria-label="Send message">Send</Button>
      </form>
    </Card>
  )
}

function ResultDetails({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data)
  return <div className="mt-2 border-t border-current/15 pt-2 text-xs text-text-secondary">{entries.map(([key, value]) => <p key={key}><span className="font-semibold capitalize">{key.replace(/_/g, ' ')}:</span> {Array.isArray(value) ? value.length : String(value)}</p>)}</div>
}