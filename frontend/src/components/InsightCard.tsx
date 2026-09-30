import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Sigma, X } from 'lucide-react'
import type { InsightDto } from '../types'

const KIND_STYLE: Record<InsightDto['kind'], { label: string; cls: string }> = {
  descriptive: { label: 'Key Insight', cls: 'bg-sky-50 text-sky-700 ring-sky-200' },
  correlational: { label: 'Association', cls: 'bg-violet-50 text-violet-700 ring-violet-200' },
  limitation: { label: 'Honest Limitation', cls: 'bg-amber-50 text-amber-700 ring-amber-200' },
}

export default function InsightCard({
  insight,
  workflowId,
}: {
  insight: InsightDto
  workflowId: string
}) {
  const [open, setOpen] = useState(false)
  const style = KIND_STYLE[insight.kind] ?? KIND_STYLE.descriptive

  return (
    <div className="glow-card fade-up p-5">
      <span
        className={`mb-3 inline-block rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest ring-1 ring-inset ${style.cls}`}
      >
        {style.label}
      </span>
      <h3 className="mb-1.5 text-[15px] font-semibold text-slate-900">{insight.title}</h3>
      <p className="text-sm leading-relaxed text-slate-600">{insight.description}</p>
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-sky-300 hover:text-sky-700"
        >
          <Sigma className="h-3.5 w-3.5" /> Explain Result
        </button>
        <Link
          to={`/evidence/${workflowId}`}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-violet-300 hover:text-violet-700"
        >
          View Evidence <ArrowRight className="h-3.5 w-3.5" />
        </Link>
        <span className="ml-auto text-[10px] text-slate-400">
          confidence {Math.round(insight.confidence * 100)}%
        </span>
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="glow-card w-full max-w-lg p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h4 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
                How did we get this?
              </h4>
              <button onClick={() => setOpen(false)} aria-label="Close">
                <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <ExplainChain insight={insight} workflowId={workflowId} />
          </div>
        </div>
      )}
    </div>
  )
}

function ExplainChain({ insight, workflowId }: { insight: InsightDto; workflowId: string }) {
  const steps: { label: string; value: string; icon?: 'sigma' }[] = [
    { label: 'Insight', value: insight.description },
  ]
  if (insight.calculation) {
    steps.push({ label: 'Calculation (deterministic engine)', value: insight.calculation, icon: 'sigma' })
  }
  return (
    <div className="flex flex-col">
      {steps.map((s, i) => (
        <div key={i} className="fade-up" style={{ animationDelay: `${i * 90}ms` }}>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              {s.icon === 'sigma' && <Sigma className="h-3 w-3" />}
              {s.label}
            </div>
            <div className="text-sm text-slate-800">{s.value}</div>
          </div>
          {i === 0 && <ArrowDown />}
        </div>
      ))}
      <div className="flex items-center justify-between rounded-xl border border-sky-200 bg-sky-50 p-3.5">
        <span className="text-sm text-sky-800">
          Full provenance: transformations → validation → dataset → Cloudinary asset
        </span>
        <Link
          to={`/evidence/${workflowId}`}
          className="ml-3 flex shrink-0 items-center gap-1 text-xs font-semibold text-sky-700 hover:text-sky-900"
        >
          View Evidence <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  )
}

function ArrowDown() {
  return (
    <div className="flex justify-center py-1">
      <div className="h-4 w-px bg-slate-300" />
    </div>
  )
}
