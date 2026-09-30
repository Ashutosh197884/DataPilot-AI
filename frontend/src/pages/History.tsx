import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Clock,
  LoaderCircle,
  ShieldCheck,
} from 'lucide-react'
import { api } from '../api/client'
import { useProject } from '../state/ProjectContext'
import type { HistoryItem, SourceDto } from '../types'

export default function HistoryPage() {
  const project = useProject()
  const navigate = useNavigate()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [sources, setSources] = useState<SourceDto[]>([])

  useEffect(() => {
    api.getHistory(project.id).then(setItems).catch(() => setItems([]))
    api.listSources().then(setSources).catch(() => setSources([]))
  }, [project.id])

  function timeAgo(iso: string): string {
    // SQLite returns tz-naive UTC timestamps; JS Date would parse them as local.
    const normalized = /[Z+]/.test(iso) ? iso : `${iso}Z`
    const s = (Date.now() - new Date(normalized).getTime()) / 1000
    if (s < 60) return 'just now'
    if (s < 3600) return `${Math.floor(s / 60)} min ago`
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`
    return `${Math.floor(s / 86400)} d ago`
  }

  return (
    <div className="mx-auto max-w-4xl pb-10">
      <h1 className="mb-6 text-xl font-semibold text-slate-900">History</h1>

      <div className="mb-10 flex flex-col gap-2">
        {items.map((h) => (
          <div key={h.id} className="glow-card flex items-center gap-4 p-4">
            {h.status === 'COMPLETED' ? (
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
            ) : h.status === 'FAILED' ? (
              <CircleAlert className="h-5 w-5 shrink-0 text-rose-500" />
            ) : (
              <LoaderCircle className="h-5 w-5 shrink-0 animate-spin text-sky-600" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800">{h.text}</p>
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <Clock className="h-3 w-3" /> {timeAgo(h.created_at)} · {h.status}
              </p>
            </div>
            {h.workflow_id && h.status === 'COMPLETED' && (
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => navigate(`/dashboard/${h.workflow_id}`)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-sky-300 hover:text-sky-700"
                >
                  Dashboard
                </button>
                <Link
                  to={`/evidence/${h.workflow_id}`}
                  className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-violet-300 hover:text-violet-700"
                >
                  Evidence <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            )}
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-slate-500">No analyses yet — ask your first question.</p>
        )}
      </div>

      {/* Permitted source registry */}
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-slate-400">
        <ShieldCheck className="h-4 w-4" /> Permitted Sources
      </h2>
      <p className="mb-4 text-xs text-slate-500">
        The orchestrator may only use sources registered here.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {sources.map((s) => (
          <div key={s.id} className="glow-card p-4">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-800">{s.name}</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ring-inset ${
                  s.allowed
                    ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                    : 'bg-slate-50 text-slate-400 ring-slate-200'
                }`}
              >
                {s.allowed ? 'allowed' : 'blocked'}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">{s.description}</p>
            <p className="mt-2 text-[11px] text-slate-400">
              {s.type} · {s.license}
              {s.last_updated ? ` · updated ${s.last_updated}` : ''}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
