import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { useProject } from '../state/ProjectContext'

const EXAMPLES = [
  'Compare rainfall and wheat production across Haryana districts from 2020 to 2025.',
  'Compare EV sales in India from 2022 to 2025 and identify the fastest-growing manufacturers.',
  'Find unusual sales spikes in the last 5 years',
  'Show me average product prices',
]

export default function HomePage() {
  const project = useProject()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function generate(q?: string) {
    const text = (q ?? query).trim()
    if (text.length < 3 || busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.runQuery(project.id, text)
      navigate(`/workflow/${res.workflow_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start workflow')
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[85vh] max-w-3xl flex-col items-center justify-center text-center">
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.3em] text-sky-700">
        Data Intelligence
      </p>
      <h1 className="mb-3 text-4xl font-bold tracking-tight text-slate-900">
        What do you want to know?
      </h1>
      <p className="mb-8 max-w-xl text-sm text-slate-500">
        Ask in plain English. DataPilot plans the workflow, gathers data from permitted
        sources, validates it, analyzes it deterministically, and shows the evidence
        behind every number.
      </p>

      <div className="glow-card w-full p-2 shadow-lg shadow-slate-200/60">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void generate()
            }
          }}
          rows={3}
          placeholder="e.g. Compare rainfall and wheat production across Haryana districts from 2020 to 2025…"
          className="w-full resize-none rounded-xl bg-transparent px-4 py-3 text-[15px] text-slate-800 placeholder:text-slate-400 focus:outline-none"
        />
        <div className="flex items-center justify-between px-2 pb-1">
          <span className="pl-2 text-[11px] text-slate-400">
            Enter to run · Shift+Enter for newline
          </span>
          <button
            onClick={() => void generate()}
            disabled={busy || query.trim().length < 3}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-sky-600/20 transition enabled:hover:brightness-110 disabled:opacity-40"
          >
            <Sparkles className="h-4 w-4" />
            {busy ? 'Starting…' : 'Generate Intelligence'}
          </button>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <div className="mt-10 w-full">
        <p className="mb-3 text-xs font-medium uppercase tracking-widest text-slate-400">
          Try asking
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuery(ex)
                void generate(ex)
              }}
              disabled={busy}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-[13px] text-slate-600 shadow-sm transition hover:border-sky-300 hover:text-slate-900 hover:shadow-md disabled:opacity-50"
            >
              “{ex}”
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
