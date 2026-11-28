import { useState } from 'react'
import type { FormEvent } from 'react'
import { saveApi, useApi } from '../../shared/api'
import type { AnalysisRun, DocumentRecord, RequirementRevision } from '../../shared/contracts'

const LIMIT = 16

export function StartForm({ onFinished, catalogRefresh = 0 }: { onFinished: () => void; catalogRefresh?: number }) {
  const documents = useApi<DocumentRecord[]>('/documents')
  const catalog = useApi<RequirementRevision | null>('/requirements/active', catalogRefresh)
  const [selected, setSelected] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const revision = catalog.state === 'ready' ? catalog.data : null
  const ready = revision !== null && revision.requirement_count > 0

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!revision || !ready || !selected.length || busy) return
    setBusy(true)
    setError('')
    setRunId(null)
    try {
      const run = await saveApi<AnalysisRun>('/analyses', 'POST', {
        document_ids: selected, revision: revision.revision,
      })
      setRunId(run.id)
      if (run.error) setError(run.error)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Не удалось запустить проверку.')
    } finally {
      setBusy(false)
      onFinished()
    }
  }

  return (
    <form className="workflow-form" onSubmit={start} aria-label="Запустить проверку">
      <h2 className="section-title">Новая проверка</h2>
      {(documents.state === 'loading' || catalog.state === 'loading') && <p role="status">Загрузка документов и каталога…</p>}
      {(documents.state === 'error' || catalog.state === 'error') && (
        <p role="alert">Не удалось загрузить документы или активную редакцию.</p>
      )}
      {catalog.state === 'ready' && ready && (
        <p>Активная редакция <strong>{revision.revision}</strong> · {revision.source}</p>
      )}
      {documents.state === 'ready' && (documents.data.length ? (
        <fieldset disabled={busy || !ready}>
          <legend>Документы для проверки · до {LIMIT}</legend>
          {documents.data.map((doc) => (
            <label className="workflow-choice" key={doc.id}>
              <input type="checkbox" checked={selected.includes(doc.id)}
                disabled={selected.length >= LIMIT && !selected.includes(doc.id)}
                onChange={(event) => {
                  const checked = event.currentTarget.checked
                  setSelected((previous) => checked ? [...previous, doc.id] : previous.filter((id) => id !== doc.id))
                }}
              />
              <span>{doc.filename}{doc.issue && <small className="muted">{doc.issue.message}</small>}</span>
            </label>
          ))}
        </fieldset>
      ) : <p>Пока нет документов. <a className="text-action" href="#documents">Загрузить PDF или DOCX</a></p>)}
      <div className="workflow-actions">
        <button type="submit" className="action action-primary" disabled={!ready || !selected.length || busy}>
          Запустить проверку
        </button>
        {busy && <p role="status">Выполняется предварительный анализ…</p>}
        {runId && <a className="text-action" href={`#analysis?run=${encodeURIComponent(runId)}`}>Открыть проверку</a>}
      </div>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
