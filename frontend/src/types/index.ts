// Shared API types mirroring the FastAPI payloads.

export interface WorkflowStepDto {
  number: number
  type: string
  title: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  output?: Record<string, unknown> | null
  error?: string | null
}

export interface WorkflowDto {
  id: string
  query_id: string
  status: 'RUNNING' | 'COMPLETED' | 'FAILED'
  started_at: string
  completed_at?: string | null
  steps: WorkflowStepDto[]
}

export interface KpiCard {
  label: string
  value: string | number
  hint?: string
}

export type ChartConfig = {
  type: 'line' | 'bar' | 'scatter' | 'table'
  title: string
  x: string
  y: string
  group?: string | null
  point_label?: string | null
  horizontal?: boolean
  columns?: string[]
  data: Record<string, unknown>[]
}

export interface InsightDto {
  id: string
  title: string
  description: string
  calculation: string
  confidence: number
  kind: 'descriptive' | 'correlational' | 'limitation'
}

export interface QualityDto {
  score: number | null
  completeness: number | null
  duplicates: number | null
  invalid: number | null
  schema_valid: boolean | null
  details: {
    name: string
    status: string
    value?: number
    detail?: string | Record<string, unknown>
  }[]
}

export interface DatasetRef {
  id: string
  name: string
  records: number
  cloudinary_public_id?: string | null
  cloudinary_url?: string | null
}

export interface DashboardDto {
  workflow_id: string
  query: string
  topic: string | null
  region: string | null
  period: (number | null)[]
  kpis: KpiCard[]
  charts: ChartConfig[]
  insights: InsightDto[]
  quality: QualityDto
  dataset: DatasetRef | null
}

export interface EvidenceItem {
  insight: { id: string; title: string; description: string; kind: string }
  calculation: string
  transformations: string[]
  dataset: {
    id: string
    name: string
    records: number
    file_type: string
    cloudinary_public_id?: string | null
    cloudinary_url?: string | null
    coverage?: string | null
    retrieved_at?: string | null
    source?: { id: string; name: string; license: string; last_updated: string } | null
  } | null
  validation: {
    quality: number
    completeness: number
    duplicates: number
    invalid: number
    schema_valid: boolean
  } | null
  source_reference: string
}

export interface EvidenceDto {
  workflow_id: string
  query: string
  chain_summary: { region: string | null; period: (number | null)[] }
  evidence_items: EvidenceItem[]
}

export interface DatasetListItem {
  id: string
  name: string
  source_type: string
  file_type: string
  records: number
  quality_score: number | null
  coverage?: string | null
  cloudinary_public_id?: string | null
  cloudinary_url?: string | null
  columns: string[]
  created_at: string
}

export interface SourceDto {
  id: string
  name: string
  type: string
  allowed: boolean
  license: string
  domain: string
  last_updated: string
  description: string
}

export interface ProjectDto {
  id: string
  name: string
  description: string
  created_at: string
}

export interface HistoryItem {
  id: string
  text: string
  status: string
  created_at: string
  workflow_id: string | null
}

export interface WorkflowEventDto {
  type: string
  workflow_id: string
  data: {
    step?: string
    title?: string
    number?: number
    output?: Record<string, unknown>
    query?: string
    error?: string
    [k: string]: unknown
  }
  at: string
}
