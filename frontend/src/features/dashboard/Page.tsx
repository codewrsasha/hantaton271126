import { ArrowRight, ClipboardList, FileChartColumn, Files, LibraryBig, ScanLine, Server, ShieldCheck } from 'lucide-react'
import { useApi } from '../../shared/api'
import type { DashboardSummary, Health } from '../../shared/contracts'

const metrics = [
  { key: 'documents', label: 'Документы', page: 'documents', icon: Files },
  { key: 'requirements', label: 'Требования', page: 'requirements', icon: LibraryBig },
  { key: 'analyses', label: 'Проверки', page: 'analysis', icon: ScanLine },
  { key: 'reports', label: 'Отчёты', page: 'reports', icon: FileChartColumn },
] as const

export default function DashboardPage({ health }: {
  health: ReturnType<typeof useApi<Health>>
}) {
  const summary = useApi<DashboardSummary>('/dashboard/summary')

  return (
    <>
      <div className="page-heading">
        <h1>Обзор</h1>
        <p>Рабочая область предварительной проверки соответствия</p>
      </div>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-art" aria-hidden="true">
          <div /><div /><div /><ShieldCheck size={94} strokeWidth={1.15} />
        </div>
        <div className="hero-content">
          <div className="hero-label"><span /> Приказ ФСТЭК России № 117</div>
          <h2 id="hero-title">Проверка<br className="hero-break" /> соответствия</h2>
          <p>Документы, нормативные требования и результаты экспертизы в локальном контуре.</p>
          <a className="primary-button" href="#documents">К документам <ArrowRight size={17} /></a>
        </div>
      </section>

      <section aria-labelledby="metrics-title" className="section-gap">
        <h2 className="section-title" id="metrics-title">Сводка</h2>
        {summary.state === 'error' &&
          <p className="inline-error" role="status">Не удалось получить сводку с локального сервера.</p>}
        <div className="metrics-grid">
          {metrics.map(({ key, label, page, icon: Icon }) => (
            <a className="panel metric" key={key} href={`#${page}`}>
              <span className="icon-tile"><Icon size={19} /></span>
              <ArrowRight className="metric-arrow" size={16} />
              <strong>{summary.state === 'ready' ? summary.data[key] : '—'}</strong>
              <span>{label}</span>
            </a>
          ))}
        </div>
      </section>

      <div className="dashboard-bottom section-gap">
        <section className="panel dashboard-panel">
          <div className="panel-heading"><ClipboardList size={20} /><h2>Проверки</h2><a href="#analysis">К анализу <ArrowRight size={15} /></a></div>
          <div className="dashboard-empty">
            <span className="icon-tile"><ScanLine size={22} /></span>
            <strong>{summary.state === 'ready' && summary.data.analyses === 0 ? 'Проверок пока нет' : 'Результаты анализа'}</strong>
            <p>{summary.state === 'ready' && summary.data.analyses === 0
              ? 'После запуска проверки здесь появится информация о ней.'
              : 'Состояние проверок доступно в разделе анализа.'}</p>
          </div>
        </section>
        <section className="panel dashboard-panel">
          <div className="panel-heading"><Server size={20} /><h2>Состояние системы</h2></div>
          <dl className="system-list">
            <div><dt>Режим работы</dt><dd>Локальный</dd></div>
            <div><dt>Backend и SQLite</dt><dd className="health-text" data-state={health.state}>{health.state === 'ready' ? 'Доступны' : health.state === 'loading' ? 'Проверка…' : 'Недоступны'}</dd></div>
            <div><dt>Языковая модель</dt><dd>Не подключена</dd></div>
          </dl>
        </section>
      </div>
    </>
  )
}
