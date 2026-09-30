import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { ProjectDto } from '../types'

const ProjectCtx = createContext<ProjectDto | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectDto | null>(null)

  useEffect(() => {
    let alive = true
    api.getOrCreateProject().then((p) => {
      if (alive) setProject(p)
    })
    return () => {
      alive = false
    }
  }, [])

  if (!project) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <span className="animate-pulse">Connecting to DataPilot…</span>
      </div>
    )
  }
  return <ProjectCtx.Provider value={project}>{children}</ProjectCtx.Provider>
}

export function useProject(): ProjectDto {
  const p = useContext(ProjectCtx)
  if (!p) throw new Error('useProject must be used within ProjectProvider')
  return p
}
