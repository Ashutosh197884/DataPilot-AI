import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Cloud, Database, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'
import ChartRenderer from '../components/ChartRenderer'
import InsightCard from '../components/InsightCard'
import type { DashboardDto } from '../types'

export default function DashboardPage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const [dash, setDash] = useState<DashboardDto | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workflowId) return
    api
      .getDashboard(workflowId)
      .then(setDash)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load dashboard'))
  }, [workflowId])

  if (error)
    return (
      <div className="mx-auto max-w-xl pt-24 text-center text-sm text-rose-600">
        {error}
        <div className="mt-3">
          <Link to="/history" className="text-sky-700 underline">
            ← back to history
          </Link>
        </div>
      </div>
    )
  if (!dash)
    return (
      <div className="pt-24 text-center text-sm text-slate-500">
        <span className="animate-pulse">Loading intelligence…</span>
      </div>
    )

  const q = dash.quality

  return (
    <div className="mx-auto max-w-5xl pb-10">
      {/* Header */}
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-sky-700">
          {dash.topic?.replaceAll('_', ' ')} {dash.region ? `· ${dash.region}` : ''}
          {dash.period[0] ? ` · ${dash.period[0]}–${dash.period[1]}` : ''}
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{dash.query}</h1>
      </div>

      {/* KPI row */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {dash.kpis.map((k) => (
          <div key={k.label} className="glow-card fade-up p-4">
            <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
              {k.label}
            </div>
            <div className="mt-1 text-2xl font-bold text-slate-900">{k.value}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="mb-8 grid gap-4 lg:grid-cols-2">
        {dash.charts.map((c) => (
          <div key={c.title} className="glow-card p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">{c.title}</h3>
            <ChartRenderer chart={c} />
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-4">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
            AI Insights
          </h2>
          {dash.insights.map((i) => (
            <InsightCard key={i.id} insight={i} workflowId={dash.workflow_id} />
          ))}
        </div>

        {/* Right rail */}
        <div className="flex flex-col gap-4">
          <div className="glow-card p-5">
            <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5" /> Data Trust
            </div>
            <TrustMeter score={q.score ?? 0} />
            <ul className="mt-4 flex flex-col gap-1.5 text-xs text-slate-600">
              <li className="flex justify-between">
                <span>Completeness</span>
                <span className="font-medium text-slate-800">{q.completeness?.toFixed(1)}%</span>
              </li>
              <li className="flex justify-between">
                <span>Duplicates</span>
                <span className="font-medium text-slate-800">{q.duplicates}</span>
              </li>
              <li className="flex justify-between">
                <span>Invalid values</span>
                <span className="font-medium text-slate-800">{q.invalid}</span>
              </li>
              <li className="flex justify-between">
                <span>Schema</span>
                <span className={q.schema_valid ? 'font-medium text-emerald-600' : 'font-medium text-amber-600'}>
                  {q.schema_valid ? 'PASS' : 'WARN'}
                </span>
              </li>
            </ul>
          </div>

          {dash.dataset && (
            <div className="glow-card p-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
                <Database className="h-3.5 w-3.5" /> Dataset
              </div>
              <p className="text-sm font-medium text-slate-800">{dash.dataset.name}</p>
              <p className="text-xs text-slate-500">
                {dash.dataset.records.toLocaleString()} records
              </p>
              {dash.dataset.cloudinary_public_id ? (
                <p className="mt-2 flex items-center gap-1.5 text-[11px] text-sky-700">
                  <Cloud className="h-3.5 w-3.5" /> Cloudinary ·{' '}
                  <span className="truncate">{dash.dataset.cloudinary_public_id}</span>
                </p>
              ) : (
                <p className="mt-2 text-[11px] text-slate-400">
                  Local asset (Cloudinary keys not configured)
                </p>
              )}
            </div>
          )}

          <Link
            to={`/evidence/${dash.workflow_id}`}
            className="glow-card group flex items-center justify-between p-5 transition hover:border-violet-300"
          >
            <span>
              <span className="block text-sm font-semibold text-slate-800">Evidence</span>
              <span className="block text-xs text-slate-500">
                See how these results were calculated
              </span>
            </span>
            <ShieldCheck className="h-5 w-5 text-violet-600 transition group-hover:scale-110" />
          </Link>
        </div>
      </div>
    </div>
  )
}

function TrustMeter({ score }: { score: number }) {
  const filled = Math.round((score / 100) * 10)
  return (
    <div>
      <div className="flex items-end justify-between">
        <span className="text-3xl font-bold text-emerald-600">{score.toFixed(1)}%</span>
        <span className="text-[10px] text-slate-400">transparent metric-based</span>
      </div>
      <div className="mt-2 flex gap-1">
        {Array.from({ length: 10 }).map((_, i) => (
          <span
            key={i}
            className={`h-2 flex-1 rounded-full ${
              i < filled ? 'bg-gradient-to-r from-emerald-500 to-sky-500' : 'bg-slate-100'
            }`}
          />
        ))}
      </div>
    </div>
  )
}
