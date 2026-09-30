import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Cloud, Database, FileDown, Filter, ShieldCheck, Sigma } from 'lucide-react'
import { api } from '../api/client'
import { useProject } from '../state/ProjectContext'
import type { EvidenceDto, HistoryItem } from '../types'

export default function EvidencePage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const project = useProject()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [ev, setEv] = useState<EvidenceDto | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getHistory(project.id).then(setHistory).catch(() => setHistory([]))
  }, [project.id])

  useEffect(() => {
    const target =
      workflowId ??
      history.find((h) => h.status === 'COMPLETED' && h.workflow_id)?.workflow_id ??
      null
    if (!target) return
    setEv(null)
    api
      .getEvidence(target)
      .then(setEv)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load evidence'))
  }, [workflowId, history])

  return (
    <div className="mx-auto max-w-3xl pb-10">
      <h1 className="mb-1 text-xl font-semibold text-slate-900">Evidence Explorer</h1>
      <p className="mb-6 text-sm text-slate-500">
        Every insight traced back to its calculation, transformations, validation,
        dataset, and original asset.
      </p>

      {/* Workflow picker */}
      <div className="mb-6 flex flex-wrap gap-2">
        {history
          .filter((h) => h.workflow_id && h.status === 'COMPLETED')
          .slice(0, 6)
          .map((h) => (
            <Link
              key={h.id}
              to={`/evidence/${h.workflow_id}`}
              className={`max-w-[280px] truncate rounded-lg border px-3 py-1.5 text-xs transition ${
                h.workflow_id === (workflowId ?? ev?.workflow_id)
                  ? 'border-violet-300 bg-violet-50 text-violet-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700'
              }`}
            >
              {h.text}
            </Link>
          ))}
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}
      {!ev && !error && (
        <p className="animate-pulse text-sm text-slate-500">Loading evidence…</p>
      )}

      {ev && (
        <>
          <div className="mb-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm">
            <span className="text-xs font-medium uppercase tracking-widest text-slate-400">Question </span>
            {ev.query}
          </div>

          {ev.evidence_items.length === 0 && (
            <p className="text-sm text-slate-500">No evidence items recorded for this run.</p>
          )}

          <div className="flex flex-col gap-10">
            {ev.evidence_items.map((item, idx) => (
              <EvidenceChain key={idx} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function ChainArrow() {
  return (
    <div className="flex justify-center py-1">
      <div className="h-5 w-px bg-gradient-to-b from-slate-300 to-slate-200" />
    </div>
  )
}

function EvidenceChain({ item }: { item: EvidenceDto['evidence_items'][number] }) {
  const download = () => {
    if (item.dataset) window.open(`/api/v1/datasets/${item.dataset.id}/download`, '_blank')
  }

  return (
    <div>
      <ChainCard accent="sky">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-sky-700">
          Insight
        </span>
        <p className="mt-1 text-sm font-medium text-slate-900">{item.insight.title}</p>
        <p className="text-xs leading-relaxed text-slate-600">{item.insight.description}</p>
      </ChainCard>
      <ChainArrow />

      {item.calculation && (
        <>
          <ChainCard accent="slate">
            <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              <Sigma className="h-3 w-3" /> Calculation
            </span>
            <code className="mt-1 block rounded-lg bg-slate-50 px-3 py-2 font-mono text-[12px] text-emerald-700 ring-1 ring-inset ring-slate-200">
              {item.calculation}
            </code>
          </ChainCard>
          <ChainArrow />
        </>
      )}

      <ChainCard accent="slate">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          <Filter className="h-3 w-3" /> Transformations ({item.transformations.length})
        </span>
        <ul className="mt-2 flex flex-col gap-1">
          {item.transformations.map((t, i) => (
            <li key={i} className="flex items-center gap-2 text-xs text-slate-700">
              <span className="text-emerald-600">✓</span> {t}
            </li>
          ))}
        </ul>
      </ChainCard>
      <ChainArrow />

      {item.validation && (
        <>
          <ChainCard accent="emerald">
            <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-emerald-700">
              <ShieldCheck className="h-3 w-3" /> Validation
            </span>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-700 sm:grid-cols-4">
              <Metric label="Quality" value={`${item.validation.quality}%`} />
              <Metric label="Completeness" value={`${item.validation.completeness}%`} />
              <Metric label="Duplicates" value={String(item.validation.duplicates)} />
              <Metric label="Invalid" value={String(item.validation.invalid)} />
            </div>
          </ChainCard>
          <ChainArrow />
        </>
      )}

      {item.dataset && (
        <>
          <ChainCard accent="slate">
            <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              <Database className="h-3 w-3" /> Dataset
            </span>
            <div className="mt-1 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-slate-800">{item.dataset.name}</p>
                <p className="text-xs text-slate-500">
                  {item.dataset.records.toLocaleString()} records
                  {item.dataset.coverage ? ` · ${item.dataset.coverage}` : ''}
                  {item.dataset.source ? ` · ${item.dataset.source.name}` : ''}
                </p>
              </div>
              <button
                onClick={download}
                className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-600 hover:border-sky-300 hover:text-sky-700"
              >
                <FileDown className="h-3.5 w-3.5" /> Asset
              </button>
            </div>
          </ChainCard>
          <ChainArrow />

          <ChainCard accent={item.dataset.cloudinary_public_id ? 'sky' : 'slate'}>
            <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-sky-700">
              <Cloud className="h-3 w-3" /> Cloudinary Asset
            </span>
            {item.dataset.cloudinary_public_id ? (
              <>
                <p className="mt-1 font-mono text-xs text-sky-800">
                  {item.dataset.cloudinary_public_id}
                </p>
                {item.dataset.cloudinary_url && (
                  <a
                    href={item.dataset.cloudinary_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block truncate text-[11px] text-sky-600 underline"
                  >
                    {item.dataset.cloudinary_url}
                  </a>
                )}
              </>
            ) : (
              <p className="mt-1 text-xs text-slate-500">
                Local asset — add CLOUDINARY_* keys to .env to store evidence on Cloudinary.
              </p>
            )}
            {item.dataset.source && (
              <p className="mt-2 border-t border-slate-100 pt-2 text-[11px] text-slate-500">
                Source: {item.dataset.source.name} · {item.dataset.source.license}
                {item.dataset.source.last_updated
                  ? ` · updated ${item.dataset.source.last_updated}`
                  : ''}
              </p>
            )}
          </ChainCard>
        </>
      )}
    </div>
  )
}

function ChainCard({
  accent,
  children,
}: {
  accent: 'sky' | 'emerald' | 'slate'
  children: React.ReactNode
}) {
  const ring =
    accent === 'sky'
      ? 'border-sky-200 bg-white'
      : accent === 'emerald'
        ? 'border-emerald-200 bg-white'
        : 'border-slate-200 bg-white'
  return (
    <div className={`fade-up rounded-xl border ${ring} p-4 shadow-sm`}>{children}</div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-100">
      <span className="block text-[10px] uppercase tracking-widest text-slate-400">
        {label}
      </span>
      <span className="block text-sm font-semibold text-slate-800">{value}</span>
    </div>
  )
}
