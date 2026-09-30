import { useMemo } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

export interface GraphStepState {
  type: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
}

const TYPE_TO_NODE: Record<string, string> = {
  intent: 'UNDERSTAND',
  source_discovery: 'SOURCES',
  collect: 'COLLECT',
  process: 'PROCESS',
  normalize_join_keys: 'PROCESS',
  join: 'PROCESS',
  aggregate: 'PROCESS',
  filter_period: 'PROCESS',
  validate: 'VALIDATE',
  analysis: 'ANALYZE',
  visualize: 'VISUALIZE',
  insights: 'INSIGHTS',
  evidence: 'EVIDENCE',
}

const PIPELINE: { id: string; label: string }[] = [
  { id: 'UNDERSTAND', label: 'Understand' },
  { id: 'SOURCES', label: 'Sources' },
  { id: 'COLLECT', label: 'Collect' },
  { id: 'PROCESS', label: 'Process' },
  { id: 'VALIDATE', label: 'Validate' },
  { id: 'ANALYZE', label: 'Analyze' },
  { id: 'VISUALIZE', label: 'Visualize' },
  { id: 'INSIGHTS', label: 'Insights' },
  { id: 'EVIDENCE', label: 'Evidence' },
]

// Light-theme status colors
const STATUS_COLOR: Record<GraphStepState['status'], string> = {
  COMPLETED: '#059669', // emerald-600
  RUNNING: '#0284c7', // sky-600
  PENDING: '#cbd5e1', // slate-300
  FAILED: '#e11d48', // rose-600
}

function PipelineNode({ data }: NodeProps) {
  const { label, color, sub } = data as { label: string; color: string; sub?: string }
  return (
    <div
      className="rounded-xl border bg-white px-4 py-2.5 text-center shadow-sm"
      style={{
        borderColor: color,
        boxShadow: `0 1px 3px ${color}22, 0 0 12px ${color}14`,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="text-[13px] font-semibold text-slate-800">{label}</div>
      {sub && <div className="text-[10px] text-slate-400">{sub}</div>}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}

const nodeTypes = { pipeline: PipelineNode }

export default function WorkflowGraph({ steps }: { steps: GraphStepState[] }) {
  const nodes: Node[] = useMemo(() => {
    const state: Record<string, GraphStepState['status']> = {}
    for (const s of steps) {
      const target = TYPE_TO_NODE[s.type]
      if (!target) continue
      const prev = state[target]
      state[target] =
        s.status === 'FAILED'
          ? 'FAILED'
          : s.status === 'RUNNING'
            ? 'RUNNING'
            : prev === 'FAILED' || prev === 'RUNNING'
              ? prev
              : s.status
    }
    return PIPELINE.map((p, i) => ({
      id: p.id,
      type: 'pipeline',
      position: { x: 240, y: i * 74 },
      data: { label: p.label, color: STATUS_COLOR[state[p.id] ?? 'PENDING'] },
      draggable: false,
    }))
  }, [steps])

  const edges: Edge[] = useMemo(
    () =>
      PIPELINE.slice(1).map((p, i) => ({
        id: `e${i}`,
        source: PIPELINE[i].id,
        target: p.id,
        animated: steps.some(
          (s) => TYPE_TO_NODE[s.type] === p.id && s.status === 'RUNNING',
        ),
        style: { stroke: '#cbd5e1' },
      })),
    [steps],
  )

  return (
    <div className="h-[420px] w-full overflow-hidden rounded-xl border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        zoomOnScroll={false}
        preventScrolling={true}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#dbe3ec" />
        <Controls showInteractive={false} className="!left-2" />
      </ReactFlow>
    </div>
  )
}
