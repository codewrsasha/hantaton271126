import { useId, useState } from 'react'
import type { AnalysisResult, ComplianceStatus, Location } from '../../shared/contracts'
import { NumberTicker } from '../../shared/NumberTicker'
import { ReviewForm } from './ReviewForm'

const statusStyles: Record<ComplianceStatus, string> = {
  'соответствует': 'match',
  'частично соответствует': 'partial',
  'не соответствует': 'gap',
  'недостаточно данных': 'unknown',
  'требуется проверка': 'review',
}

const statuses = Object.keys(statusStyles) as ComplianceStatus[]

const relations = {
  supports: 'Подтверждает',
  contradicts: 'Противоречит',
  context: 'Контекст',
}

function displayedStatus(result: AnalysisResult) {
  return result.review?.corrected_status ?? result.status
}

function formatLocation(location: Location) {
  if (location.kind === 'pdf_page') return `Страница ${location.page}`
  if (location.kind === 'docx_section') return `Раздел ${location.section}`
  return 'Точное место не определено'
}

function ResultDetails({ result, runId, completed, onSaved }: {
  result: AnalysisResult
  runId: string
  completed: boolean
  onSaved: (result: AnalysisResult) => void
}) {
  return (
    <details className="result-details">
      <summary aria-label={`Подробности требования ${result.requirement_id}`}>Подробности</summary>
      <div className="result-detail">
        <p>{result.requirement_text}</p>
        <div><strong>Обоснование</strong><p>{result.explanation}</p></div>
        {result.evidence.length > 0 && (
          <ul className="evidence-list">
            {result.evidence.map((item, index) => (
              <li key={index}>
                <p className="evidence-location">
                  <a className="text-action" href={`#documents?document=${encodeURIComponent(item.document_id)}`}>{item.filename}</a>
                  <span className="muted">
                    Фрагмент {index + 1} · {formatLocation(item.location)} · {relations[result.review?.evidence_relations?.[index] ?? item.relation]}
                  </span>
                </p>
                <blockquote className="whitespace-pre-wrap">{item.excerpt}</blockquote>
              </li>
            ))}
          </ul>
        )}
        {result.review && (
          <div>
            <strong>Экспертная проверка</strong>
            <p>{result.review.comment}</p>
            {result.review.corrected_status && <p className="muted">Исходный статус: {result.status}</p>}
          </div>
        )}
        {completed && <ReviewForm runId={runId} result={result} statuses={statuses} onSaved={onSaved} />}
      </div>
    </details>
  )
}

export function RunResults({ runId, initialResults, completed }: {
  runId: string
  initialResults: AnalysisResult[]
  completed: boolean
}) {
  const [updated, setUpdated] = useState<Map<string, AnalysisResult>>(() => new Map())
  const results = initialResults.map((result) => updated.get(result.requirement_id) ?? result)
  const [filter, setFilter] = useState<ComplianceStatus | 'all'>('all')
  const filterId = useId()
  const visible = filter === 'all' ? results : results.filter((result) => displayedStatus(result) === filter)
  const counts: Record<ComplianceStatus, number> = {
    'соответствует': 0,
    'частично соответствует': 0,
    'не соответствует': 0,
    'недостаточно данных': 0,
    'требуется проверка': 0,
  }
  for (const result of results) counts[displayedStatus(result)] += 1

  return (
    <section className="run-results" aria-label="Результаты проверки">
      {completed && (
        <div className="score-band">
          <div>
            <strong className="score-number"><NumberTicker value={counts['соответствует'] / results.length} ratio /></strong>
            <p>Доля требований со статусом «соответствует»</p>
            <p className="muted">Предварительная оценка · {counts['соответствует']} из {results.length}</p>
          </div>
          <div>
            <div className="distribution" aria-hidden="true">
              {statuses.filter((status) => counts[status]).map((status) => (
                <span key={status} data-tone={statusStyles[status]} style={{ flexGrow: counts[status] }} />
              ))}
            </div>
            <dl className="distribution-legend">
              {statuses.map((status) => (
                <div key={status} data-tone={statusStyles[status]}><dt>{status}</dt><dd>{counts[status]}</dd></div>
              ))}
            </dl>
          </div>
        </div>
      )}

      <div className="result-toolbar">
        <h4>Результаты по требованиям</h4>
        <div className="filter">
          <label htmlFor={filterId}>Статус</label>
          <select id={filterId} value={filter}
            onChange={(event) => setFilter(event.currentTarget.value as ComplianceStatus | 'all')}>
            <option value="all">Все статусы</option>
            {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </div>
      </div>

      {visible.length ? (
        <>
          <p className="table-narrow-note muted">Прокрутите таблицу, чтобы увидеть все столбцы.</p>
          <div className="table-scroll" tabIndex={0} role="region" aria-label="Таблица требований">
            <table className="results-table">
              <thead><tr><th scope="col">Требование</th><th scope="col">Статус</th><th scope="col">Источник</th></tr></thead>
              <tbody className="stagger-list">
                {visible.map((result) => {
                  const status = displayedStatus(result)
                  const source = result.source_reference
                  const citation = new URLSearchParams({
                    requirement: result.requirement_id,
                    revision: source.revision,
                    clause: source.clause,
                  })
                  return (
                    <tr key={result.requirement_id}>
                      <td>
                        <strong>{result.requirement_id}</strong>
                        <ResultDetails result={result} runId={runId} completed={completed}
                          onSaved={(item) => setUpdated((previous) => new Map(previous).set(item.requirement_id, item))} />
                      </td>
                      <td><span className="compliance-status" data-tone={statusStyles[status]}>{status}</span></td>
                      <td>
                        <a className="text-action" href={`#requirements?${citation}`}>
                          Приказ № {source.order_number}, пункт {source.clause}
                        </a>
                        <p className="muted">Редакция {source.revision}</p>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : <p className="module-state">Требований с таким статусом нет.</p>}
    </section>
  )
}
