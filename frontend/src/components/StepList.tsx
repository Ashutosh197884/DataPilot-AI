import { CheckCircle2, CircleDashed, LoaderCircle, XCircle } from 'lucide-react'
import type { WorkflowStepDto } from '../types'

function compactOutput(step: WorkflowStepDto): string {
  const o = step.output as Record<string, unknown> | null
  if (!o) return ''
  if (step.type === 'validate' && typeof o.summary === 'string') return o.summary
  if (step.type === 'collect' && typeof o.rows === 'number') {
    return `${o.rows.toLocaleString()} rows · ${(o.columns as string[] | undefined)?.length ?? '?'} cols`
  }
  if (step.type === 'intent') {
    const q = o.clarifying_questions as string[] | undefined
    return q && q.length ? `needs input: ${q[0]}` : typeof o.summary === 'string' ? o.summary : ''
  }
  if (step.type === 'insights' && typeof o.insights === 'number') {
    const kpis = Array.isArray(o.kpis) ? o.kpis.length : 0
    return `${o.insights} insights · ${kpis} KPIs`
  }
  return ''
}

export default function StepList({ steps }: { steps: WorkflowStepDto[] }) {
  return (
    <ol className="flex flex-col gap-1.5">
      {steps.map((s) => (
        <li
          key={s.number}
          className={`flex items-start gap-3 rounded-lg px-3 py-2 ${
            s.status === 'RUNNING' ? 'step-running bg-sky-50' : ''
          }`}
        >
          <span className="mt-0.5 shrink-0">
            {s.status === 'COMPLETED' && (
              <CheckCircle2 className="h-4.5 w-4.5 text-emerald-600" />
            )}
            {s.status === 'RUNNING' && (
              <LoaderCircle className="h-4.5 w-4.5 animate-spin text-sky-600" />
            )}
            {s.status === 'PENDING' && <CircleDashed className="h-4.5 w-4.5 text-slate-300" />}
            {s.status === 'FAILED' && <XCircle className="h-4.5 w-4.5 text-rose-500" />}
          </span>
          <span className="min-w-0">
            <span
              className={`block truncate text-sm ${
                s.status === 'PENDING'
                  ? 'text-slate-400'
                  : s.status === 'FAILED'
                    ? 'text-rose-600'
                    : 'text-slate-800'
              }`}
            >
              {s.title}
            </span>
            {(compactOutput(s) || s.error) && (
              <span
                className={`block truncate text-xs ${
                  s.error ? 'text-rose-500' : 'text-slate-500'
                }`}
              >
                {s.error ?? compactOutput(s)}
              </span>
            )}
          </span>
        </li>
      ))}
    </ol>
  )
}
