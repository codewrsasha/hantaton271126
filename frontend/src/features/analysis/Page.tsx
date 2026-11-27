import { ScanLine } from 'lucide-react'
import { ModulePage } from '../../shared/ModulePage'
import type { AnalysisRun } from '../../shared/contracts'

const labels: Record<AnalysisRun['state'], string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершена',
  failed: 'Ошибка',
}

export default function AnalysisPage() {
  return (
    <ModulePage<AnalysisRun[]>
      title="Анализ соответствия"
      description="Сопоставление документов с требованиями и проверка доказательств экспертом."
      icon={ScanLine}
      path="/analyses"
      emptyTitle="Проверок пока нет"
      emptyDescription="Запуск проверок появится после подключения извлечения текста, базы требований и локального поиска."
    >
      {(runs) => runs.length ? <ul className="resource-list">{runs.map((run) =>
        <li key={run.id}>{labels[run.state]} · Результатов по требованиям: {run.results.length}</li>)}</ul> : null}
    </ModulePage>
  )
}
