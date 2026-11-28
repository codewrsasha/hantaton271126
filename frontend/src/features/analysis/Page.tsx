import { useCallback, useEffect, useRef, useState } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import type { AnalysisRun, DocumentRecord } from '../../shared/contracts'
import { RequirementsOverlay } from '../requirements/Page'
import { RunResults } from './RunResults'
import { StartForm } from './StartForm'
import '../../shared/workflow.css'

const labels: Record<AnalysisRun['state'], string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершена',
  failed: 'Завершилась с ошибкой',
}

const documentLabels: Record<DocumentRecord['state'], string> = {
  received: 'Получен',
  extracted: 'Текст извлечён',
  needs_review: 'Требуется проверка извлечения',
  failed: 'Ошибка извлечения',
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

function Runs({ runs, runId, reload }: { runs: AnalysisRun[]; runId: string | null; reload: () => void }) {
  const visible = runId ? runs.filter((run) => run.id === runId) : runs
  const inProgress = visible.some((run) => run.state === 'running' || run.state === 'queued')
  useEffect(() => {
    if (!inProgress) return
    const timer = window.setTimeout(reload, 1500)
    return () => window.clearTimeout(timer)
  }, [inProgress, reload])

  return (
    <>
      {runId && <p className="source-navigation"><a className="text-action" href="#analysis">Все проверки</a></p>}
      {visible.length ? (
        <ul className="run-list stagger-list">
          {visible.map((run) => (
            <li key={run.id} className="run" data-state={run.state}>
              <header className="run-header">
                <div>
                  <h3>{labels[run.state]}</h3>
                  <p className="muted run-id">{new Date(run.created_at).toLocaleString('ru-RU')} · {run.id}</p>
                </div>
                <span className="muted">Документов: {run.document_ids.length}</span>
              </header>
              <RunTimeline run={run} />
              <p>Редакция <strong>{run.revision}</strong> · {run.source}</p>
              <ul className="run-documents">
                {run.documents.map((doc) => (
                  <li key={doc.id}>
                    <a className="text-action" href={`#documents?document=${encodeURIComponent(doc.id)}`}>{doc.filename}</a>
                    <p className="muted">{documentLabels[doc.state]} · фрагментов: {doc.fragment_count}</p>
                    {doc.issue && <p className="muted">{doc.issue.message}</p>}
                  </li>
                ))}
              </ul>
              {run.error && <p role="alert">{run.error}</p>}
              {run.results.length > 0 && <RunResults runId={run.id} initialResults={run.results} completed={run.state === 'completed'} />}
            </li>
          ))}
        </ul>
      ) : <p className="module-state">Проверка не найдена.</p>}
    </>
  )
}

export default function AnalysisPage({ query }: { query?: string }) {
  const params = new URLSearchParams(query)
  const runId = params.get('run')
  const linkedCatalog = params.get('catalog') === '1'
  const [catalogOpen, setCatalogOpen] = useState(linkedCatalog)
  const [catalogRefresh, setCatalogRefresh] = useState(0)
  const catalogButton = useRef<HTMLButtonElement>(null)
  const [refresh, setRefresh] = useState(0)
  const reload = useCallback(() => setRefresh((value) => value + 1), [])

  return (
    <ModulePage<AnalysisRun[]>
      title="Анализ соответствия"
      description="Предварительные результаты для проверки специалистом."
      path="/analyses"
      refresh={refresh}
      beforeData={(
        <>
          <div className="analysis-catalog-action">
            <button id="open-requirements" ref={catalogButton} className="action action-primary catalog-button" aria-haspopup="dialog"
              onClick={() => setCatalogOpen(true)}>База требований</button>
            {catalogOpen && <RequirementsOverlay query={linkedCatalog ? query : undefined} close={() => {
              setCatalogOpen(false)
              setCatalogRefresh((value) => value + 1)
              if (linkedCatalog) {
                const runQuery = runId ? '?' + new URLSearchParams({ run: runId }) : ''
                window.history.replaceState(null, '', '#analysis' + runQuery)
                window.dispatchEvent(new Event('hashchange'))
              }
              requestAnimationFrame(() => (catalogButton.current ?? document.getElementById('open-requirements'))?.focus())
            }} />}
          </div>
          {!runId && <StartForm catalogRefresh={catalogRefresh} onFinished={reload} />}
        </>
      )}
      sectionTitle="Проверки"
      emptyTitle="Проверок пока нет"
      emptyDescription="Выберите документы и запустите предварительный анализ."
    >
      {(runs) => runs.length || runId ? <Runs runs={runs} runId={runId} reload={reload} /> : null}
    </ModulePage>
  )
}
