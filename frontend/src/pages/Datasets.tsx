import { useCallback, useEffect, useRef, useState } from 'react'
import { Cloud, CloudUpload, FileDown, LoaderCircle } from 'lucide-react'
import { api } from '../api/client'
import { useProject } from '../state/ProjectContext'
import type { DatasetListItem } from '../types'

interface DatasetDetail {
  id: string
  name: string
  source_type: string
  records: number
  quality_score: number | null
  coverage?: string | null
  cloudinary_public_id?: string | null
  cloudinary_url?: string | null
  schema: { columns: { name: string; type: string }[] }
  preview: Record<string, unknown>[]
  validation: {
    completeness: number | null
    duplicates: number | null
    invalid: number | null
    schema_valid: boolean | null
  } | null
}

export default function DatasetsPage() {
  const project = useProject()
  const [datasets, setDatasets] = useState<DatasetListItem[]>([])
  const [selected, setSelected] = useState<DatasetDetail | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(() => {
    api.listDatasets(project.id).then(setDatasets).catch(() => setDatasets([]))
  }, [project.id])

  useEffect(refresh, [refresh])

  async function openDetail(id: string) {
    setSelected(null)
    const res = await fetch(`/api/v1/datasets/${id}`).then((r) => r.json())
    setSelected(res as DatasetDetail)
  }

  async function upload(file: File) {
    setUploading(true)
    setUploadMsg(null)
    try {
      // Preferred path: signed direct-to-Cloudinary. Falls back to the
      // multipart endpoint (Cloudinary when configured, local storage otherwise).
      try {
        const sig = await api.getUploadSignature()
        const form = new FormData()
        form.append('file', file)
        form.append('api_key', sig.api_key)
        form.append('timestamp', String(sig.timestamp))
        form.append('signature', sig.signature)
        form.append('folder', sig.folder)
        const res = await fetch(sig.upload_url, { method: 'POST', body: form })
        if (!res.ok) throw new Error('cloudinary upload failed')
      } catch {
        /* fall through to multipart */
      }
      await api.uploadMultipart(project.id, file)
      setUploadMsg(`Uploaded “${file.name}” — schema inferred, validation queued.`)
      refresh()
    } catch (e) {
      setUploadMsg(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl pb-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Datasets</h1>
          <p className="text-sm text-slate-500">
            Assets managed via Cloudinary · schema inferred on upload
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void upload(f)
              e.target.value = ''
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-600/20 transition enabled:hover:brightness-110 disabled:opacity-50"
          >
            {uploading ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <CloudUpload className="h-4 w-4" />
            )}
            {uploading ? 'Uploading…' : '+ Upload Dataset'}
          </button>
        </div>
      </div>

      {uploadMsg && (
        <p className="mb-4 rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-xs text-sky-800">
          {uploadMsg}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-2">
          {datasets.map((d) => (
            <button
              key={d.id}
              onClick={() => void openDetail(d.id)}
              className={`glow-card flex items-center gap-4 p-4 text-left transition hover:border-sky-300 ${
                selected?.id === d.id ? 'border-sky-400 ring-1 ring-sky-200' : ''
              }`}
            >
              <Cloud className="h-5 w-5 shrink-0 text-sky-600" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-800">
                  {d.name}
                </span>
                <span className="block text-xs text-slate-500">
                  {d.records.toLocaleString()} records · {d.file_type}
                  {d.coverage ? ` · ${d.coverage}` : ''}
                </span>
              </span>
              {d.quality_score != null && (
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
                    d.quality_score >= 97
                      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                      : d.quality_score >= 90
                        ? 'bg-amber-50 text-amber-700 ring-amber-200'
                        : 'bg-rose-50 text-rose-700 ring-rose-200'
                  }`}
                >
                  {d.quality_score.toFixed(1)}%
                </span>
              )}
            </button>
          ))}
          {datasets.length === 0 && (
            <p className="text-sm text-slate-500">No datasets yet — upload one above.</p>
          )}
        </div>

        {/* Detail panel */}
        <div>
          {selected ? (
            <div className="glow-card sticky top-6 p-5">
              <h3 className="mb-1 text-sm font-semibold text-slate-900">{selected.name}</h3>
              <p className="mb-4 text-xs text-slate-500">
                {selected.records.toLocaleString()} records ·{' '}
                {selected.schema.columns.length} columns
              </p>

              <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Schema
              </h4>
              <table className="mb-4 w-full text-left text-xs">
                <tbody>
                  {selected.schema.columns.map((c) => (
                    <tr key={c.name} className="border-b border-slate-100">
                      <td className="py-1.5 font-mono text-slate-700">{c.name}</td>
                      <td className="py-1.5 text-right text-slate-400">{c.type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {selected.validation && (
                <>
                  <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                    Data Quality
                  </h4>
                  <div className="mb-4 grid grid-cols-2 gap-2 text-xs">
                    <Metric label="Completeness" value={`${selected.validation.completeness}%`} />
                    <Metric label="Duplicates" value={String(selected.validation.duplicates)} />
                    <Metric label="Invalid" value={String(selected.validation.invalid)} />
                    <Metric
                      label="Schema"
                      value={selected.validation.schema_valid ? 'PASS' : 'WARN'}
                    />
                  </div>
                </>
              )}

              <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Preview
              </h4>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500">
                      {selected.schema.columns.map((c) => (
                        <th key={c.name} className="border-b border-slate-200 px-2 py-1.5">
                          {c.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selected.preview.map((row, i) => (
                      <tr key={i} className="text-slate-700">
                        {selected.schema.columns.map((c) => (
                          <td key={c.name} className="border-b border-slate-100 px-2 py-1">
                            {String(row[c.name] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <button
                onClick={() =>
                  window.open(`/api/v1/datasets/${selected.id}/download`, '_blank')
                }
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 hover:border-sky-300 hover:text-sky-700"
              >
                <FileDown className="h-3.5 w-3.5" /> Download asset
              </button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Select a dataset to inspect its schema.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-100">
      <span className="block text-[10px] uppercase tracking-widest text-slate-400">{label}</span>
      <span className="block text-sm font-semibold text-slate-800">{value}</span>
    </div>
  )
}
