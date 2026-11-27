import { useLayoutEffect, useRef, useSyncExternalStore } from 'react'
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
  { id: 'requirements', label: 'Требования', component: RequirementsPage },
  { id: 'analysis', label: 'Анализ', component: AnalysisPage },
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
  const [route, query] = hash.split('?')
  const active = pages.find((page) => page.id === route) ?? pages[0]
  const Page = active.component
  const health = useApi<Health>('/health', active.id)
  const nav = useRef<HTMLElement>(null)
  const main = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    window.scrollTo(0, 0)
  }, [hash])

  useLayoutEffect(() => {
    const container = nav.current
    const link = container?.querySelector<HTMLElement>('[aria-current="page"]')
    if (!container || !link) return

    const alignIndicator = () => {
      container.style.setProperty('--indicator-x', `${link.offsetLeft}px`)
      container.style.setProperty('--indicator-y', `${link.offsetTop + link.offsetHeight - 2}px`)
      container.style.setProperty('--indicator-width', `${link.offsetWidth}px`)
      container.dataset.indicator = 'ready'
    }

    alignIndicator()
    const observer = new ResizeObserver(alignIndicator)
    for (const item of container.querySelectorAll('a')) observer.observe(item)
    observer.observe(container)
    return () => observer.disconnect()
  }, [active.id])

  return (
    <>
      <a className="skip-link" href="#main" onClick={(event) => {
        event.preventDefault()
        main.current?.focus()
      }}>К содержанию</a>
      <header className="app-header">
        <div className="header-inner">
          <a className="brand" href="#dashboard">Инспектор <span>ФСТЭК</span></a>
          <nav ref={nav} className="navigation" aria-label="Разделы приложения">
            {pages.map(({ id, label }) => (
              <a key={id} href={`#${id}`} aria-current={id === active.id ? 'page' : undefined}>
                {label}
              </a>
            ))}
            <span className="nav-indicator" aria-hidden="true" />
          </nav>
          <div className="connection" data-state={health.state} role="status">
            {connectionLabels[health.state]}
          </div>
        </div>
      </header>

      <main className="content page-enter" id="main" ref={main} tabIndex={-1} key={hash}>
        <Page health={health} query={query} />
      </main>

      <footer className="app-footer">
        <div className="footer-inner">Локальный контур</div>
      </footer>
    </>
  )
}
