import { NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import {
  Boxes,
  Database,
  GitBranch,
  History,
  Home,
  ShieldCheck,
} from 'lucide-react'
import { ProjectProvider } from './state/ProjectContext'
import HomePage from './pages/Home'
import WorkflowLivePage from './pages/WorkflowLive'
import DashboardPage from './pages/Dashboard'
import DatasetsPage from './pages/Datasets'
import EvidencePage from './pages/Evidence'
import HistoryPage from './pages/History'

const navItems = [
  { to: '/', label: 'Workspace', icon: Home, end: true },
  { to: '/datasets', label: 'Datasets', icon: Database },
  { to: '/workflows', label: 'Workflows', icon: GitBranch },
  { to: '/evidence', label: 'Evidence', icon: ShieldCheck },
  { to: '/history', label: 'History', icon: History },
]

export default function App() {
  return (
    <ProjectProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 px-8 py-6 lg:px-12">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/workflow/:workflowId" element={<WorkflowLivePage />} />
            <Route path="/dashboard/:workflowId" element={<DashboardPage />} />
            <Route path="/datasets" element={<DatasetsPage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/evidence/:workflowId" element={<EvidencePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </main>
      </div>
    </ProjectProvider>
  )
}

function Sidebar() {
  const navigate = useNavigate()
  return (
    <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-slate-200 bg-white px-4 py-6">
      <button
        onClick={() => navigate('/')}
        className="mb-8 flex items-center gap-2.5 rounded-lg px-2 py-1 text-left"
      >
        <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-sky-600 to-indigo-600 shadow-md shadow-sky-600/20">
          <Boxes className="h-5 w-5 text-white" />
        </span>
        <span>
          <span className="block text-sm font-semibold tracking-tight text-slate-800">
            DataPilot AI
          </span>
          <span className="block text-[11px] text-slate-500">data intelligence</span>
        </span>
      </button>

      <button
        onClick={() => navigate('/')}
        className="mb-6 w-full rounded-lg bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 ring-1 ring-inset ring-sky-200 transition hover:bg-sky-100"
      >
        + New Query
      </button>

      <nav className="flex flex-col gap-1">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                isActive
                  ? 'bg-slate-100 font-medium text-slate-900'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-500">
        <span className="font-medium text-slate-600">Own-engine AI.</span> Deterministic
        analysis · auditable evidence · Cloudinary asset layer.
      </div>
    </aside>
  )
}
