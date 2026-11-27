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
  { id: 'dashboard', label: 'Обзор', component: DashboardPage },
  { id: 'documents', label: 'Документы', component: DocumentsPage },
  { id: 'requirements', label: 'База требований', component: RequirementsPage },
  { id: 'analysis', label: 'Анализ соответствия', component: AnalysisPage },
  { id: 'reports', label: 'Отчёты', component: ReportsPage },
  { id: 'chat', label: 'ИИ-чат', component: ChatPage },
]

const connectionLabels = {
  loading: 'Проверка связи…',
  ready: 'Сервер подключён',
  error: 'Сервер недоступен',
}

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
        <div className="brand"><a href="#dashboard">Инспектор ФСТЭК</a></div>
        <nav className="navigation" aria-label="Разделы приложения">
          {pages.map(({ id, label }) => (
            <a key={id} href={`#${id}`} aria-current={id === active.id ? 'page' : undefined}>
              {label}
            </a>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <span>Локальный режим</span>
          <span className="connection" data-state={health.state} role="status">
            {connectionLabels[health.state]}
          </span>
        </header>
        <main className="content" key={active.id}><Page health={health} /></main>
      </div>
    </div>
  )
}
