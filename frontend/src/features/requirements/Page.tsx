import { ModulePage } from '../../shared/ModulePage'
import type { Requirement } from '../../shared/contracts'

export default function RequirementsPage() {
  return (
    <ModulePage<Requirement[]>
      title="База требований"
      description="Приказ ФСТЭК России № 117."
      path="/requirements"
      emptyTitle="База требований пока пуста"
      emptyDescription="Требования появятся после загрузки проверенной редакции приказа."
    >
      {(requirements) => requirements.length ? <ul className="resource-list">{requirements.map((item) =>
        <li key={item.requirement_id}>
          <strong>Пункт {item.source_reference.clause}, редакция {item.source_reference.revision}</strong>
          <p>{item.requirement_text}</p>
        </li>)}</ul> : null}
    </ModulePage>
  )
}
