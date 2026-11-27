import { ModulePage } from '../../shared/ModulePage'
import type { DocumentRecord } from '../../shared/contracts'

export default function DocumentsPage() {
  return (
    <ModulePage<DocumentRecord[]>
      title="Документы"
      description="Материалы для проверки в формате PDF или DOCX."
      path="/documents"
      emptyTitle="Документов пока нет"
      emptyDescription="Загрузка файлов пока недоступна."
    >
      {(documents) => documents.length ? <ul className="resource-list">{documents.map((doc) =>
        <li key={doc.id} className="resource-row">
          <span>{doc.filename}</span>
          <span className="muted">{doc.format.toUpperCase()}</span>
        </li>)}</ul> : null}
    </ModulePage>
  )
}
