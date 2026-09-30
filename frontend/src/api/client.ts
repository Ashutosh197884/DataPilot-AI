import type {
  DashboardDto,
  DatasetListItem,
  EvidenceDto,
  HistoryItem,
  ProjectDto,
  SourceDto,
  WorkflowDto,
  WorkflowEventDto,
} from '../types'

const BASE = '/api/v1'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail ?? detail
    } catch {
      /* keep statusText */
    }
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // ---- bootstrap ----
  async getOrCreateProject(): Promise<ProjectDto> {
    const list = await req<ProjectDto[]>('GET', '/projects')
    if (list.length) return list[0]
    return req<ProjectDto>('POST', '/projects', {
      name: 'Demo Project',
      description: 'Default workspace',
    })
  },

  // ---- queries / workflows ----
  runQuery: (projectId: string, query: string) =>
    req<{ query_id: string; workflow_id: string; status: string }>('POST', '/queries', {
      project_id: projectId,
      query,
    }),

  getWorkflow: (id: string) => req<WorkflowDto>('GET', `/workflows/${id}`),
  getDashboard: (id: string) => req<DashboardDto>('GET', `/workflows/${id}/dashboard`),
  getEvidence: (id: string) => req<EvidenceDto>('GET', `/workflows/${id}/evidence`),

  // ---- history ----
  getHistory: (projectId: string) =>
    req<HistoryItem[]>('GET', `/projects/${projectId}/queries`),

  // ---- datasets ----
  listDatasets: (projectId: string) =>
    req<DatasetListItem[]>('GET', `/datasets?project_id=${projectId}`),
  getUploadSignature: () =>
    req<{
      cloud_name: string
      api_key: string
      timestamp: number
      folder: string
      signature: string
      upload_url: string
    }>('GET', '/datasets/upload-signature'),

  uploadMultipart: (projectId: string, file: File, name?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('project_id', projectId)
    if (name) form.append('name', name)
    return fetch(`${BASE}/datasets/upload`, { method: 'POST', body: form }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed (${r.status})`)
      return r.json()
    })
  },

  // ---- sources ----
  listSources: () => req<SourceDto[]>('GET', '/sources'),
}

/** Subscribe to the SSE event stream of a workflow run. */
export function subscribeWorkflowEvents(
  workflowId: string,
  onEvent: (e: WorkflowEventDto) => void,
  onDone?: () => void,
): () => void {
  const es = new EventSource(`${BASE}/workflows/${workflowId}/events`)
  const types = [
    'workflow.started',
    'workflow.step.started',
    'workflow.step.completed',
    'workflow.completed',
    'workflow.failed',
  ]
  const handlers = types.map((t) => {
    const h = (ev: MessageEvent) => {
      try {
        onEvent(JSON.parse(ev.data) as WorkflowEventDto)
      } catch {
        /* ignore malformed */
      }
      if (t === 'workflow.completed' || t === 'workflow.failed') {
        es.close()
        onDone?.()
      }
    }
    es.addEventListener(t, h as EventListener)
    return { t, h }
  })
  es.onerror = () => {
    /* server ends stream after completion; router handles final state */
  }
  return () => {
    handlers.forEach(({ t, h }) => es.removeEventListener(t, h as EventListener))
    es.close()
  }
}
