import { useState } from 'react'
import type { FormEvent } from 'react'
import { saveApi } from '../../shared/api'
import type { AnalysisResult, ComplianceStatus, EvidenceRelation } from '../../shared/contracts'

export function ReviewForm({ runId, result, statuses, onSaved }: {
  runId: string
  result: AnalysisResult
  statuses: ComplianceStatus[]
  onSaved: (result: AnalysisResult) => void
}) {
  const [comment, setComment] = useState(result.review?.comment ?? '')
  const [status, setStatus] = useState<ComplianceStatus | ''>(result.review?.corrected_status ?? '')
  const [relations, setRelations] = useState<Record<number, EvidenceRelation>>(result.review?.evidence_relations ?? {})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!comment.trim() || busy) return
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const updated = await saveApi<AnalysisResult>(
        `/analyses/${encodeURIComponent(runId)}/results/${encodeURIComponent(result.requirement_id)}/review`,
        'PUT', { comment, corrected_status: status || null, evidence_relations: relations },
      )
      onSaved(updated)
      setSaved(true)
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Не удалось сохранить правку.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="workflow-form review-form" onSubmit={submit} aria-label="Экспертная правка">
      <fieldset disabled={busy}>
        <legend>Экспертная правка</legend>
        <label>Статус после проверки
          <select value={status} onChange={(event) => setStatus(event.currentTarget.value as ComplianceStatus | '')}>
            <option value="">Оставить исходный статус</option>
            {statuses.map((option) => <option key={option}>{option}</option>)}
          </select>
        </label>
        {result.evidence.length > 0 && <p className="muted">Отметьте, как цитаты связаны с требованием.</p>}
        {result.evidence.map((item, index) => (
          <label key={index}>Фрагмент {index + 1} · {item.filename}
            <select value={relations[index] ?? item.relation} onChange={(event) => {
              const relation = event.currentTarget.value as EvidenceRelation
              setRelations((previous) => ({ ...previous, [index]: relation }))
            }}>
              <option value="context">Контекст</option>
              <option value="supports" disabled={item.location.kind === 'unknown'}>Подтверждает</option>
              <option value="contradicts">Противоречит</option>
            </select>
          </label>
        ))}
        <label>Комментарий эксперта
          <textarea required maxLength={4000} rows={3} value={comment}
            onChange={(event) => setComment(event.currentTarget.value)} />
        </label>
        <button type="submit" className="action action-primary" disabled={!comment.trim() || busy}>
          {busy ? 'Сохраняется…' : 'Сохранить правку'}
        </button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">Экспертная правка сохранена.</p>}
    </form>
  )
}
