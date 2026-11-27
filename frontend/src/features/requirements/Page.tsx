import { LibraryBig } from 'lucide-react'
import { ModulePage } from '../../shared/ModulePage'
import type { Requirement } from '../../shared/contracts'

export default function RequirementsPage() {
  return (
    <ModulePage<Requirement[]>
      title="База требований"
      description="Требования приказа ФСТЭК России № 117 с указанием редакции и пункта."
      icon={LibraryBig}
      path="/requirements"
      emptyTitle="Требования ещё не импортированы"
      emptyDescription="База будет заполнена после проверки нормативного источника и его редакции."
    >
      {(requirements) => requirements.length ? <ul className="resource-list">{requirements.map((item) =>
        <li key={item.requirement_id}>
          <strong>Пункт {item.source_reference.clause}, редакция {item.source_reference.revision}</strong>
          <p>{item.requirement_text}</p>
        </li>)}</ul> : null}
    </ModulePage>
  )
}
