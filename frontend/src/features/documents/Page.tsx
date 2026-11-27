import { Files } from 'lucide-react'
import { ModulePage } from '../../shared/ModulePage'
import type { DocumentRecord } from '../../shared/contracts'

export default function DocumentsPage() {
  return (
    <ModulePage<DocumentRecord[]>
      title="Документы"
      description="Исходные материалы для предварительной проверки."
      icon={Files}
      path="/documents"
      emptyTitle="Документов пока нет"
      emptyDescription="Загрузка и извлечение текста из PDF и DOCX запланированы на следующий этап."
    >
      {(documents) => documents.length ? <ul className="resource-list">{documents.map((doc) =>
        <li key={doc.id}>{doc.filename} · {doc.format.toUpperCase()}</li>)}</ul> : null}
    </ModulePage>
  )
}
