import { useEffect, useState } from 'react'
import { useApi } from '../../shared/api'
import type { ChatStatus, DashboardSummary, Health } from '../../shared/contracts'
import { NumberTicker } from '../../shared/NumberTicker'

const metrics = [
  { key: 'documents', label: 'Документы', page: 'documents' },
  { key: 'requirements', label: 'Требования активной редакции', page: 'analysis?catalog=1' },
  { key: 'analyses', label: 'Проверки', page: 'analysis' },
  { key: 'reports', label: 'Отчёты', page: 'reports' },
] as const

const availability = {
  loading: 'Проверка связи…',
  ready: 'Доступны',
  error: 'Недоступны',
}

let titleRevealed = false

export default function DashboardPage({ health }: {
  health: ReturnType<typeof useApi<Health>>
}) {
  const summary = useApi<DashboardSummary>('/dashboard/summary')
  const chat = useApi<ChatStatus>('/chat/status')
  const [animateTitle] = useState(() => !titleRevealed)
  useEffect(() => { titleRevealed = true }, [])

  return (
    <>
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Предварительный анализ</p>
          <h1 className={animateTitle ? 'focus-title' : undefined} aria-label="Проверка соответствия">
            <span>Проверка</span><span>соответствия</span>
          </h1>
          <a className="action action-primary" href="#documents">Подготовить проверку</a>
        </div>
        <div className="order-grid">
          <p>Приказ ФСТЭК России</p>
          <p className="order-number"><span>№</span> 117</p>
          <a className="text-action" href="#analysis?catalog=1">К базе требований</a>
        </div>
      </header>

      <section className="dashboard-section scene-reveal" aria-labelledby="metrics-title">
        <h2 className="section-title" id="metrics-title">Сводка</h2>
        <ul className="metrics" aria-busy={summary.state === 'loading'}>
          {metrics.map(({ key, label, page }) => (
            <li key={key}>
              <a className="metric" href={`#${page}`}>
                <span className="metric-label">{label}</span>
                {summary.state === 'ready' && <strong className="metric-value"><NumberTicker value={summary.data[key]} /></strong>}
                {summary.state === 'loading' && <span className="skeleton metric-skeleton" aria-hidden="true" />}
                {summary.state === 'error' && <span className="muted">Нет данных</span>}
              </a>
            </li>
          ))}
        </ul>
        {summary.state === 'error' && (
          <p className="summary-error" role="status">Не удалось получить сводку с локального сервера.</p>
        )}
      </section>

      <div className="overview-details scene-reveal">
        <section aria-labelledby="checks-title">
          <div className="section-heading-with-action">
            <h2 className="section-title" id="checks-title">Проверки</h2>
            <a className="text-action" href="#analysis">Открыть анализ</a>
          </div>
          <div className="module-state" aria-live="polite">
            {summary.state === 'loading' && <p className="muted">Загрузка проверок…</p>}
            {summary.state === 'error' && <p className="muted">Сведения о проверках недоступны.</p>}
            {summary.state === 'ready' && (
              <p>{summary.data.analyses === 0 ? 'Проверок пока нет' : 'Результаты доступны в разделе анализа.'}</p>
            )}
          </div>
        </section>

        <section aria-labelledby="system-title">
          <h2 className="section-title" id="system-title">Состояние системы</h2>
          <dl className="system-list">
            <div><dt>Режим работы</dt><dd>Локальный</dd></div>
            <div><dt>Сервер и база данных</dt><dd>{availability[health.state]}</dd></div>
            <div><dt>ИИ-чат</dt><dd>{chat.state === 'ready'
              ? chat.data.state === 'ready' ? 'Доступен' : 'Не подключён'
              : chat.state === 'error' ? 'Нет данных' : 'Проверка связи…'}</dd></div>
          </dl>
        </section>
      </div>
    </>
  )
}
