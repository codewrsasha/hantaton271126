import { useRef, useState } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import type { AnalysisRun } from '../../shared/contracts'
import { RequirementsOverlay } from '../requirements/Page'
import { RunResults } from './RunResults'

const labels: Record<AnalysisRun['state'], string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершена',
  failed: 'Завершилась с ошибкой',
}

function RunTimeline({ run }: { run: AnalysisRun }) {
  const phase = run.state === 'queued' ? 0 : run.state === 'running' ? 1 : 2
  const phases = ['Ожидание', 'Анализ', run.state === 'failed' ? 'Ошибка' : 'Результаты']

  return (
    <>
      <ol className="timeline" aria-label="Состояния проверки" data-running={run.state === 'running'}>
        {phases.map((label, index) => (
          <li key={label} aria-current={index === phase ? 'step' : undefined}
            data-complete={index < phase && run.state !== 'failed'}>
            {label}
          </li>
        ))}
      </ol>
      {run.state === 'running' && (
        <div className="indeterminate" role="progressbar" aria-label="Анализ выполняется"
          aria-valuetext="Точный прогресс неизвестен"><span /></div>
      )}
    </>
  )
}

export default function AnalysisPage({ query }: { query?: string }) {
  const params = new URLSearchParams(query)
  const runId = params.get('run')
  const linkedCatalog = params.get('catalog') === '1'
  const [catalogOpen, setCatalogOpen] = useState(linkedCatalog)
  const catalogButton = useRef<HTMLButtonElement>(null)

  return (
    <ModulePage<AnalysisRun[]>
      title="Анализ соответствия"
      description="Ход проверки и предварительные результаты по требованиям."
      path="/analyses"
      sectionTitle="Проверки"
      emptyTitle="Проверок пока нет"
      emptyDescription="Запуск анализа станет доступен после подключения обработки документов."
      beforeData={<div className="analysis-catalog-action">
        <button id="open-requirements" ref={catalogButton} className="action action-primary catalog-button" aria-haspopup="dialog"
          onClick={() => setCatalogOpen(true)}>База требований</button>
        {catalogOpen && <RequirementsOverlay query={linkedCatalog ? query : undefined} close={() => {
          setCatalogOpen(false)
          if (linkedCatalog) {
            const runQuery = runId ? '?' + new URLSearchParams({ run: runId }) : ''
            window.history.replaceState(null, '', '#analysis' + runQuery)
            window.dispatchEvent(new Event('hashchange'))
          }
          requestAnimationFrame(() => (catalogButton.current ?? document.getElementById('open-requirements'))?.focus())
        }} />}
      </div>}
    >
      {(runs) => {
        if (!runs.length && !runId) return null
        const visibleRuns = runId ? runs.filter((run) => run.id === runId) : runs
        return (
          <>
            {runId && <p className="source-navigation"><a className="text-action" href="#analysis">Все проверки</a></p>}
            {visibleRuns.length ? (
              <ul className="run-list stagger-list">
                {visibleRuns.map((run) => (
                  <li key={run.id} className="run" data-state={run.state}>
                    <header className="run-header">
                      <div><h3>{labels[run.state]}</h3><p className="muted run-id">{run.id}</p></div>
                      <span className="muted">Документов: {run.document_ids.length}</span>
                    </header>
                    <RunTimeline run={run} />
                    {run.results.length > 0 && <RunResults results={run.results} completed={run.state === 'completed'} />}
                    {!run.results.length && run.state === 'completed' && <p className="module-state">Нет результатов по требованиям.</p>}
                  </li>
                ))}
              </ul>
            ) : <p className="module-state">Проверка не найдена.</p>}
          </>
        )
      }}
    </ModulePage>
  )
}
