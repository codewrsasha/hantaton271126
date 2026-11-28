import { useState } from 'react'
import type { FormEvent } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import { saveApi, useApi } from '../../shared/api'
import type { AnalysisRun, Report } from '../../shared/contracts'
import '../../shared/workflow.css'

function ReportForm({ onCreated }: { onCreated: () => void }) {
  const runs = useApi<AnalysisRun[]>('/analyses')
  const completed = runs.state === 'ready' ? runs.data.filter((run) => run.state === 'completed') : []
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || busy) return
    setMessage('')
    setError('')
    setBusy(true)
    try {
      await saveApi<Report>('/reports', 'POST', { analysis_id: selected })
      setMessage('Отчёт сохранён и доступен для скачивания.')
      onCreated()
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Не удалось сформировать отчёт.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="workflow-form" onSubmit={create} aria-label="Сформировать отчёт">
      <h2 className="section-title">Новый отчёт</h2>
      {runs.state === 'loading' && <p role="status">Загрузка проверок…</p>}
      {runs.state === 'error' && <p role="alert">Не удалось загрузить проверки.</p>}
      {runs.state === 'ready' && !completed.length && (
        <p>Для отчёта нужна завершённая <a className="text-action" href="#analysis">проверка</a>.</p>
      )}
      {completed.length > 0 && (
        <label>Завершённая проверка
          <select required value={selected} onChange={(event) => setSelected(event.currentTarget.value)} disabled={busy}>
            <option value="">Выберите проверку</option>
            {completed.map((run) => (
              <option key={run.id} value={run.id}>
                {new Date(run.created_at).toLocaleString('ru-RU')} · {run.revision} · {run.id}
              </option>
            ))}
          </select>
        </label>
      )}
      <button type="submit" className="action action-primary" disabled={!selected || busy}>
        {busy ? 'Формируется…' : 'Сформировать отчёт'}
      </button>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </form>
  )
}

function ReportDownload({ report }: { report: Report }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function download() {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/v1/reports/${encodeURIComponent(report.id)}/download`)
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: unknown } | null
        throw new Error(typeof body?.detail === 'string' ? body.detail : 'Не удалось скачать отчёт.')
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = report.filename
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (problem) {
      setError(problem instanceof TypeError ? 'Не удалось связаться с локальным сервером.'
        : problem instanceof Error ? problem.message : 'Не удалось скачать отчёт.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" className="text-action" disabled={busy} onClick={download}
        aria-label={`Скачать отчёт ${report.filename}`}>{busy ? 'Скачивается…' : 'Скачать HTML'}</button>
      {error && <p className="report-download-error" role="alert">{error}</p>}
    </>
  )
}

export default function ReportsPage() {
  const [refresh, setRefresh] = useState(0)
  return (
    <ModulePage<Report[]>
      title="Отчёты"
      description="Предварительные отчёты о пробелах с цитатами и реквизитами источников."
      path="/reports"
      refresh={refresh}
      beforeData={<ReportForm onCreated={() => setRefresh((value) => value + 1)} />}
      sectionTitle="Сформированные отчёты"
      emptyTitle="Отчётов пока нет"
      emptyDescription="Выберите завершённую проверку и сформируйте отчёт."
    >
      {(reports) => reports.length ? (
        <ul className="resource-list stagger-list">
          {reports.map((report) => (
            <li key={report.id} className="resource-row">
              <span className="entry-name">{report.filename}</span>
              <a className="text-action" href={`#analysis?run=${encodeURIComponent(report.analysis_id)}`}>К проверке</a>
              <ReportDownload report={report} />
            </li>
          ))}
        </ul>
      ) : null}
    </ModulePage>
  )
}
