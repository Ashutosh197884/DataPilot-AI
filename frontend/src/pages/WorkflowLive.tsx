import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, CircleAlert, ListTree } from 'lucide-react'
import { api, subscribeWorkflowEvents } from '../api/client'
import StepList from '../components/StepList'
import WorkflowGraph from '../components/WorkflowGraph'
import type { WorkflowEventDto, WorkflowStepDto } from '../types'

type Phase = 'running' | 'completed' | 'failed'

export default function WorkflowLivePage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const [steps, setSteps] = useState<WorkflowStepDto[]>([])
  const [phase, setPhase] = useState<Phase>('running')
  const [error, setError] = useState<string | null>(null)
  const navigatedRef = useRef(false)

  useEffect(() => {
    if (!workflowId) return
    let cleanup = () => {}
    let alive = true

    api.getWorkflow(workflowId).then((wf) => {
      if (!alive) return
      setSteps(wf.steps)
      if (wf.status === 'COMPLETED') finish('completed')
      else if (wf.status === 'FAILED') finish('failed')
      else {
        cleanup = subscribeWorkflowEvents(
          workflowId,
          (e) => handleEvent(e),
          () => {},
        )
      }
    })

    function handleEvent(e: WorkflowEventDto) {
      if (!alive) return
      if (e.type === 'workflow.step.started') {
        upsert(e.data.number!, 'RUNNING')
      }
      if (e.type === 'workflow.step.completed') {
        upsert(e.data.number!, 'COMPLETED', e.data.output)
      }
      if (e.type === 'workflow.completed') finish('completed')
      if (e.type === 'workflow.failed') {
        setError((e.data.error as string) ?? 'Workflow failed')
        finish('failed')
      }
    }

    function upsert(number: number, status: WorkflowStepDto['status'], output?: Record<string, unknown>) {
      setSteps((prev) => {
        const idx = prev.findIndex((s) => s.number === number)
        if (idx === -1) return prev
        const next = [...prev]
        next[idx] = { ...next[idx], status, output: output ?? next[idx].output }
        return next
      })
    }

    function finish(p: Phase) {
      if (!alive || navigatedRef.current) return
      navigatedRef.current = true
      setPhase(p)
    }

    return () => {
      alive = false
      cleanup()
    }
  }, [workflowId])

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Workflow</h1>
          <p className="text-xs text-slate-400">{workflowId}</p>
        </div>
        {phase === 'completed' && (
          <Link
            to={`/dashboard/${workflowId}`}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-600/20 transition hover:brightness-110"
          >
            Open Intelligence Dashboard <ArrowRight className="h-4 w-4" />
          </Link>
        )}
        {phase === 'failed' && (
          <span className="flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-2 text-sm text-rose-600 ring-1 ring-inset ring-rose-200">
            <CircleAlert className="h-4 w-4" /> Failed — {error}
          </span>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
        <WorkflowGraph steps={steps.map((s) => ({ type: s.type, status: s.status }))} />
        <div className="glow-card p-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-400">
            <ListTree className="h-3.5 w-3.5" /> Steps
          </div>
          <StepList steps={steps} />
        </div>
      </div>

      {phase === 'completed' && (
        <p className="mt-6 text-center text-sm text-sky-700">
          Intelligence ready — open the dashboard above.
        </p>
      )}
    </div>
  )
}
