import type { ReactNode } from 'react'
import { useApi } from './api'

interface ModulePageProps<T> {
  title: string
  description: string
  path: string
  emptyTitle: string
  emptyDescription: string
  children: (data: T) => ReactNode
}

export function ModulePage<T>({
  title, description, path, emptyTitle, emptyDescription, children,
}: ModulePageProps<T>) {
  const result = useApi<T>(path)

  return (
    <>
      <header className="page-heading">
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </header>
      <div className="surface" aria-live="polite">
        {result.state === 'loading' && (
          <p className="module-state muted">Загрузка данных…</p>
        )}
        {result.state === 'error' && (
          <div className="module-state">
            <h2>Не удалось получить данные</h2>
            <p className="muted">Проверьте, запущен ли локальный сервер.</p>
          </div>
        )}
        {result.state === 'ready' && (children(result.data) ?? (
          <div className="module-state">
            <h2>{emptyTitle}</h2>
            <p className="muted">{emptyDescription}</p>
          </div>
        ))}
      </div>
    </>
  )
}
