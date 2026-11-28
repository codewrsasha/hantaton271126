import type { ReactNode } from 'react'
import { useApi } from './api'

interface ModulePageProps<T> {
  title: string
  description: string
  path: string
  emptyTitle: string
  emptyDescription: string
  sectionTitle?: string
  beforeData?: ReactNode
  children: (data: T) => ReactNode
}

export function ModulePage<T>({
  title, description, path, emptyTitle, emptyDescription, sectionTitle, beforeData, children,
}: ModulePageProps<T>) {
  const result = useApi<T>(path)

  return (
    <>
      <header className="page-heading">
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </header>
      {beforeData}
      <section className="module-data scene-reveal" aria-label={sectionTitle ?? title} aria-busy={result.state === 'loading'}>
        {sectionTitle && <h2 className="section-title">{sectionTitle}</h2>}
        {result.state === 'loading' && (
          <div className="module-state skeleton-state" role="status">
            <span className="sr-only">Загрузка данных…</span>
            <span className="skeleton" aria-hidden="true" />
            <span className="skeleton" aria-hidden="true" />
          </div>
        )}
        {result.state === 'error' && (
          <div className="module-state" role="status">
            <strong>Не удалось получить данные</strong>
            <p className="muted">Проверьте, запущен ли локальный сервер.</p>
          </div>
        )}
        {result.state === 'ready' && (children(result.data) ?? (
          <div className="module-state">
            <strong>{emptyTitle}</strong>
            <p className="muted">{emptyDescription}</p>
          </div>
        ))}
      </section>
    </>
  )
}
