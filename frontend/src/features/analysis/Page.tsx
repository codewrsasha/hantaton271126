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
      description="Сопоставление документов с требованиями приказа."
      path="/analyses"
      emptyTitle="Проверок пока нет"
      emptyDescription="Для запуска проверки нужны документы, требования и локальный поиск."
    >
      {(runs) => runs.length ? <ul className="resource-list">{runs.map((run) =>
        <li key={run.id} className="resource-row">
          <span>{labels[run.state]}</span>
          <span className="muted">Результатов по требованиям: {run.results.length}</span>
        </li>)}</ul> : null}
    </ModulePage>
  )
}
