import { FileChartColumn, Files, LayoutDashboard, LibraryBig, LockKeyhole, MessagesSquare, ScanLine, ShieldCheck } from 'lucide-react'
import { useSyncExternalStore } from 'react'
import AnalysisPage from '../features/analysis/Page'
import ChatPage from '../features/chat/Page'
import DashboardPage from '../features/dashboard/Page'
import DocumentsPage from '../features/documents/Page'
import ReportsPage from '../features/reports/Page'
import RequirementsPage from '../features/requirements/Page'
import { useApi } from '../shared/api'
import type { Health } from '../shared/contracts'

const pages = [
  { id: 'dashboard', label: 'Обзор', icon: LayoutDashboard, component: DashboardPage },
  { id: 'documents', label: 'Документы', icon: Files, component: DocumentsPage },
  { id: 'requirements', label: 'База требований', icon: LibraryBig, component: RequirementsPage },
  { id: 'analysis', label: 'Анализ соответствия', icon: ScanLine, component: AnalysisPage },
  { id: 'reports', label: 'Отчёты', icon: FileChartColumn, component: ReportsPage },
  { id: 'chat', label: 'ИИ-чат', icon: MessagesSquare, component: ChatPage },
]

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

function currentHash() {
  return window.location.hash.slice(1)
}

export default function App() {
  const hash = useSyncExternalStore(subscribe, currentHash)
  const active = pages.find((page) => page.id === hash) ?? pages[0]
  const Page = active.component
  const health = useApi<Health>('/health', active.id)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#dashboard">
          <span className="brand-icon"><ShieldCheck size={23} strokeWidth={2.1} /></span>
          <span><strong>FSTEC Inspector</strong><small>Предварительный аудит</small></span>
        </a>
        <nav className="navigation" aria-label="Разделы приложения">
          {pages.map(({ id, label, icon: Icon }) => (
            <a key={id} href={`#${id}`} aria-current={id === active.id ? 'page' : undefined}>
              <Icon size={19} strokeWidth={1.8} /><span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-footer">
          <LockKeyhole size={17} />
          <div><strong>Локальный контур</strong><small>On-premise</small></div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <span className="breadcrumb">Рабочая область <span aria-hidden="true">/</span> <b>{active.label}</b></span>
          <span className="connection" data-state={health.state} role="status">
            {health.state === 'ready' ? 'Сервер подключён' : health.state === 'loading' ? 'Проверка сервера' : 'Сервер недоступен'}
          </span>
        </header>
        <main className="content" key={active.id}><Page health={health} /></main>
      </div>
    </div>
  )
}
