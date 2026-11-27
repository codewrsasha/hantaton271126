import { CircleAlert, LoaderCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useApi } from './api'

interface ModulePageProps<T> {
  title: string
  description: string
  icon: LucideIcon
  path: string
  emptyTitle: string
  emptyDescription: string
  children: (data: T) => ReactNode
}

export function ModulePage<T>({
  title, description, icon: Icon, path, emptyTitle, emptyDescription, children,
}: ModulePageProps<T>) {
  const result = useApi<T>(path)

  return (
    <>
      <div className="page-heading">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <section className="panel empty-module" aria-live="polite">
        {result.state === 'loading' && (
          <div className="empty-state"><LoaderCircle className="animate-spin" /><p>Загрузка данных…</p></div>
        )}
        {result.state === 'error' && (
          <div className="empty-state"><CircleAlert /><p>Не удалось получить данные. Проверьте подключение к локальному серверу.</p></div>
        )}
        {result.state === 'ready' && (children(result.data) ?? (
          <div className="empty-state">
            <div className="icon-tile"><Icon size={23} /></div>
            <h2>{emptyTitle}</h2>
            <p>{emptyDescription}</p>
          </div>
        ))}
      </section>
    </>
  )
}
