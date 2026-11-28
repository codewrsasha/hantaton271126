import { ModulePage } from '../../shared/ModulePage'
import type { Requirement } from '../../shared/contracts'

export default function RequirementsPage({ query }: { query?: string }) {
  const params = new URLSearchParams(query)
  const requirementId = params.get('requirement')
  const revision = params.get('revision')
  const clause = params.get('clause')
  return (
    <ModulePage<Requirement[]>
      title="База требований"
      description="Приказ ФСТЭК России № 117."
      path="/requirements"
      sectionTitle="Нормативный текст"
      emptyTitle="База требований пока пуста"
      emptyDescription="Требования появятся после загрузки проверенной редакции приказа."
    >
      {(requirements) => {
        if (!requirements.length && !requirementId) return null
        const visible = requirementId
          ? requirements.filter((item) =>
            item.requirement_id === requirementId &&
            (revision === null || item.source_reference.revision === revision) &&
            (clause === null || item.source_reference.clause === clause),
          )
          : requirements
        return (
          <>
            {requirementId && (
              <p className="source-navigation"><a className="text-action" href="#requirements">Все требования</a></p>
            )}
            {visible.length ? (
              <ul className="resource-list stagger-list">
                {visible.map((item) => (
                  <li key={JSON.stringify([item.requirement_id, item.source_reference.revision])} className="catalog-entry">
                    <p className="entry-name">Пункт {item.source_reference.clause}</p>
                    <div><p>{item.requirement_text}</p><p className="muted">Редакция {item.source_reference.revision}</p></div>
                  </li>
                ))}
              </ul>
            ) : <p className="module-state">Требование не найдено в локальной базе.</p>}
          </>
        )
      }}
    </ModulePage>
  )
}
