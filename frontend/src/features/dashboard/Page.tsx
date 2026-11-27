import { useApi } from '../../shared/api'
import type { DashboardSummary, Health } from '../../shared/contracts'

const metrics = [
  { key: 'documents', label: 'Документы', page: 'documents' },
  { key: 'requirements', label: 'Требования', page: 'requirements' },
  { key: 'analyses', label: 'Проверки', page: 'analysis' },
  { key: 'reports', label: 'Отчёты', page: 'reports' },
] as const

const availability = {
  loading: 'Проверка связи…',
  ready: 'Доступны',
  error: 'Недоступны',
}

export default function DashboardPage({ health }: {
  health: ReturnType<typeof useApi<Health>>
}) {
  const summary = useApi<DashboardSummary>('/dashboard/summary')

  return (
    <>
      <header className="page-heading overview-heading">
        <div>
          <p className="page-context">Приказ ФСТЭК России № 117</p>
          <h1>Обзор проверок</h1>
        </div>
        <a className="primary-action" href="#documents">Открыть документы</a>
      </header>

      <section aria-labelledby="metrics-title">
        <h2 className="section-heading" id="metrics-title">Сводка</h2>
        <ul className="surface metrics" aria-busy={summary.state === 'loading'}>
          {metrics.map(({ key, label, page }) => (
            <li key={key}>
              <a className="metric" href={`#${page}`}>
                <span className="metric-label">{label}</span>
                {summary.state === 'ready'
                  ? <strong className="metric-value">{summary.data[key]}</strong>
                  : <span className="metric-placeholder">
                      {summary.state === 'loading' ? 'Загрузка…' : 'Нет данных'}
                    </span>}
              </a>
            </li>
          ))}
        </ul>
        {summary.state === 'error' && (
          <p className="summary-error" role="status">Не удалось получить сводку с локального сервера.</p>
        )}
      </section>

      <div className="overview-details">
        <section aria-labelledby="checks-title">
          <div className="section-heading section-heading-with-action">
            <h2 id="checks-title">Проверки</h2>
            <a className="text-action" href="#analysis">Открыть анализ</a>
          </div>
          <div className="surface check-state" aria-live="polite">
            {summary.state === 'loading' && <p className="muted">Загрузка проверок…</p>}
            {summary.state === 'error' && <p className="muted">Сведения о проверках недоступны.</p>}
            {summary.state === 'ready' && (
              summary.data.analyses === 0
                ? <p>Проверок пока нет</p>
                : <p>Результаты доступны в разделе анализа.</p>
            )}
          </div>
        </section>

        <section aria-labelledby="system-title">
          <h2 className="section-heading" id="system-title">Состояние системы</h2>
          <dl className="system-list">
            <div><dt>Режим работы</dt><dd>Локальный</dd></div>
            <div><dt>Сервер и база данных</dt><dd className="availability" data-state={health.state}>{availability[health.state]}</dd></div>
            <div><dt>Языковая модель</dt><dd>Не подключена</dd></div>
          </dl>
        </section>
      </div>
    </>
  )
}
