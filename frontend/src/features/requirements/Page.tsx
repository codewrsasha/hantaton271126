import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import { useApi } from '../../shared/api'
import type { Requirement, RequirementRevision } from '../../shared/contracts'
import { DocumentConverter } from './DocumentConverter'
import type { Conversion } from './DocumentConverter'
import './styles.css'

const states = { draft: 'Черновик', published: 'Опубликована', archived: 'В архиве' }
const revisionsPath = '/requirements/revisions'
const maxPackageBytes = 4 * 1024 * 1024

async function write(path: string, method: 'POST' | 'DELETE', body?: File | FormData) {
  const response = await fetch('/api/v1' + path, {
    method, body,
    headers: { 'X-Catalog-Action': '1', ...(body instanceof File ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'Сервер отклонил операцию.')
  }
  return response
}

async function post(path: string, body?: File) {
  const response = await write(path, 'POST', body)
  const data = await response.json()
  return { revision: data as RequirementRevision, created: response.status === 201 }
}

function Entries({ revision, id, clause }: { revision: string; id: string | null; clause: string | null }) {
  const result = useApi<Requirement[]>(`${revisionsPath}/${encodeURIComponent(revision)}/requirements`)
  if (result.state === 'loading') return <p role="status">Загрузка требований…</p>
  if (result.state === 'error') return <p role="alert">Не удалось загрузить требования редакции.</p>
  const visible = id ? result.data.filter(r => r.requirement_id === id && r.source_reference.clause === clause) : result.data
  if (!visible.length) return <p role="status">{id ? 'Требование по этой ссылке не найдено.' : 'В выбранной редакции нет требований.'}</p>
  return <ul className="resource-list catalog-entries">{visible.map(r => (
    <li key={r.requirement_id}>
      <details open={id === r.requirement_id || undefined}>
        <summary className="catalog-item"><strong>Пункт {r.source_reference.clause}</strong><span className="muted">{r.requirement_id}</span></summary>
        <p className="normative-text">{r.requirement_text}</p>
      </details>
    </li>
  ))}</ul>
}

function RevisionDialog({ row, id, clause, close, changed, deleted }: {
  row: RequirementRevision; id: string | null; clause: string | null
  close: () => void; changed: (row: RequirementRevision) => void
  deleted: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const mounted = useRef(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => {
    const element = dialog.current!
    mounted.current = true
    element.showModal()
    return () => {
      mounted.current = false
      element.close()
    }
  }, [])

  async function action(operation: string, question: string, success: string) {
    if (!window.confirm(question)) return
    setBusy(true)
    setMessage('Сохранение…')
    try {
      const path = `${revisionsPath}/${encodeURIComponent(row.revision)}`
      if (operation === 'delete') {
        await write(path, 'DELETE')
        deleted()
      } else {
        const result = await post(`${path}/${operation}`)
        changed(result.revision)
        if (mounted.current) setMessage(success)
      }
    } catch (error) {
      if (mounted.current) setMessage(error instanceof Error ? error.message : 'Не удалось сохранить изменение.')
    } finally {
      if (mounted.current) setBusy(false)
    }
  }

  return <dialog ref={dialog} className="catalog-dialog" aria-labelledby="revision-title"
    onCancel={event => { event.preventDefault(); if (!busy) close() }}>
    <header>
      <div><p className="muted">{states[row.state]}{row.active && ' · активна'}</p>
        <h2 id="revision-title">Редакция {row.revision}</h2></div>
      <button autoFocus className="action catalog-button" disabled={busy} onClick={close}>Закрыть</button>
    </header>
    <div className="catalog-dialog-content">
      <dl className="revision-meta">
        <dt>Дата редакции</dt><dd>{row.revision_date}</dd>
        <dt>Источник</dt><dd>{row.source}</dd>
        <dt>Дата получения</dt><dd>{row.obtained_on}</dd>
        <dt>Импорт</dt><dd>{new Date(row.imported_at).toLocaleString('ru-RU')}</dd>
        <dt>SHA-256 пакета</dt><dd><code>{row.sha256}</code></dd>
        <dt>Сверка с источником</dt><dd>{row.reviewed_at
          ? 'Подтверждена пользователем ' + new Date(row.reviewed_at).toLocaleString('ru-RU')
          : 'Ручная сверка не подтверждена'}</dd>
      </dl>
      <h3>Нормативный текст · {row.requirement_count}</h3>
      <Entries revision={row.revision} id={id} clause={clause} />
    </div>
    <footer>
      <p role="status">{message}</p>
      <div className="catalog-actions">
        {row.state === 'archived' && <button disabled={busy} className="action catalog-button catalog-delete" onClick={() =>
          void action('delete', `Удалить редакцию «${row.revision}» и все её требования без возможности восстановления? Ссылки на эти требования перестанут работать.`, '')}>Удалить из архива</button>}
        {row.active && <button disabled={busy} className="action catalog-button" onClick={() =>
          void action('deactivate', 'Снять редакцию с использования?', 'Редакция снята с использования.')}>Снять с использования</button>}
        {row.state === 'published' && !row.active && <button disabled={busy} className="action catalog-button" onClick={() =>
          void action('activate', 'Использовать эту редакцию для новых проверок?', 'Активная редакция выбрана.')}>Сделать активной</button>}
        {row.state !== 'archived' && <button disabled={busy || row.active} className="action catalog-button" onClick={() =>
          void action('archive', 'Перенести редакцию в архив без возможности повторной публикации?', 'Редакция в архиве.')}>Архивировать</button>}
        {row.state === 'draft' && <button disabled={busy} className="action action-primary catalog-button" onClick={() =>
          void action('publish', 'Вы сверили текст и реквизиты с официальным источником и подтверждаете публикацию?', 'Сверка зафиксирована. Редакция опубликована.')}>Опубликовать</button>}
      </div>
      {row.active && <p className="muted">Чтобы архивировать редакцию, сначала снимите её с использования.</p>}
    </footer>
  </dialog>
}

export function RequirementsOverlay({ query, close }: { query?: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => element.close()
  }, [])

  return <dialog ref={dialog} className="catalog-dialog requirements-overlay" aria-labelledby="requirements-title"
    onCancel={event => { event.preventDefault(); close() }}>
    <header>
      <div>
        <h2 id="requirements-title">База требований</h2>
        <p className="muted">Приказ ФСТЭК России № 117</p>
      </div>
      <button autoFocus className="action catalog-button" onClick={close}>Закрыть каталог</button>
    </header>
    <div className="catalog-dialog-content">
      <RequirementsCatalog query={query} />
    </div>
  </dialog>
}

function RequirementsCatalog({ query }: { query?: string }) {
  const [refresh, setRefresh] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [drafts, setDrafts] = useState<Array<{ id: number; filename: string; conversion: Conversion }>>([])
  const nextDraftId = useRef(0)
  const [showArchive, setShowArchive] = useState(false)
  const params = new URLSearchParams(query)
  const id = params.get('requirement'), revision = params.get('revision'), clause = params.get('clause')
  const citation = params.has('requirement') || params.has('clause')
  const invalid = (citation && (!id || !clause || !revision)) || (params.has('revision') && !revision)
    || ['requirement', 'revision', 'clause'].some(key => params.getAll(key).length > 1)
  const [selected, setSelected] = useState(revision)
  const [followCitation, setFollowCitation] = useState(true)
  const [updates, setUpdates] = useState<Record<string, RequirementRevision>>({})
  const [activeOverride, setActiveOverride] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  async function importFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.currentTarget.files ?? [])
    event.currentTarget.value = ''
    if (!files.length) return
    setBusy(true)
    setErrors([])
    let added = 0
    let repeated = 0
    let converted = 0
    const failures: string[] = []
    for (const [index, file] of files.entries()) {
      setMessage(`Обработка файла ${index + 1} из ${files.length}…`)
      try {
        if (/\.json$/i.test(file.name)) {
          if (file.size > maxPackageBytes) throw new Error('Размер JSON превышает 4 МиБ.')
          const result = await post(revisionsPath, file)
          if (result.created) added++
          else repeated++
        } else {
          const form = new FormData()
          form.append('file', file)
          const response = await write('/requirements/convert', 'POST', form)
          const conversion: Conversion = await response.json()
          const draft = { id: nextDraftId.current++, filename: file.name, conversion }
          setDrafts(current => [...current, draft])
          converted++
        }
      } catch (error) {
        failures.push(`${index + 1}. ${file.name}: ${error instanceof Error ? error.message : 'Ошибка импорта.'}`)
      }
    }
    setMessage(`Добавлено редакций: ${added}. Уже в базе: ${repeated}. Подготовлено к сверке: ${converted}. Ошибок: ${failures.length}.`)
    setErrors(failures)
    setUpdates({})
    setActiveOverride(null)
    setRefresh(n => n + 1)
    setBusy(false)
  }

  const draft = drafts[0]
  const nextDraft = () => setDrafts(current => current.slice(1))

  return <ModulePage<RequirementRevision[]> title="База требований" description="Приказ ФСТЭК России № 117." hideHeading
    path={revisionsPath} refresh={refresh} sectionTitle="Редакции" emptyTitle="База требований пока пуста"
    emptyDescription="Нажмите «Добавить требования», чтобы загрузить первый пакет." beforeData={
      <div className="catalog-import">
        <input ref={picker} type="file" accept=".json,.pdf,.docx,.rtf,.txt,.md,.markdown,.rst,.csv,.tsv,.html,.htm"
          multiple hidden onChange={importFiles} />
        <button className="action action-primary catalog-button" disabled={busy} onClick={() => picker.current?.click()}>+ Добавить требования</button>
        <p className="muted">Выберите файлы разных форматов одновременно. JSON до 4 МиБ добавляется сразу, остальные документы автоматически преобразуются для сверки.</p>
        <p className="muted">JSON, PDF с текстом, DOCX, RTF, TXT, Markdown, RST, CSV, TSV и HTML.</p>
        <p role="status">{message}</p>
        {!!errors.length && <ul className="catalog-errors" role="alert">{errors.map(error => <li key={error}>{error}</li>)}</ul>}
        {drafts.length > 1 && <p className="muted">Черновиков на сверку: {drafts.length}</p>}
        {draft && <DocumentConverter key={draft.id} disabled={busy} draft={draft.conversion}
          filename={draft.filename} discard={nextDraft}
          save={async file => {
            const result = await post(revisionsPath, file)
            setRefresh(n => n + 1)
            setMessage(result.created ? 'Редакция добавлена в каталог как черновик.' : 'Этот пакет уже есть в каталоге.')
            nextDraft()
          }} />}
      </div>
    }>
    {data => {
      const rows = data.map(original => {
        const row = Object.hasOwn(updates, original.revision) ? updates[original.revision] : original
        return activeOverride === null ? row : { ...row, active: row.revision === activeOverride }
      })
      const active = rows.find(row => row.active)
      const chosen = rows.find(row => row.revision === selected)
      const archivedCount = rows.filter(row => row.state === 'archived').length
      const visibleRows = showArchive ? rows : rows.filter(row => row.state !== 'archived')
      const badLink = followCitation && (invalid || (selected !== null && !chosen))
      if (!rows.length && !badLink) return null
      return <div className="revision-catalog">
        <div className="catalog-toolbar">
          <p>Активная редакция: <strong>{active?.revision ?? 'не выбрана'}</strong></p>
          {archivedCount > 0 && <button className="action catalog-button" aria-expanded={showArchive} aria-controls="catalog-cards"
            onClick={() => setShowArchive(value => !value)}>
            {showArchive ? 'Скрыть архив' : `Показать архив (${archivedCount})`}
          </button>}
        </div>
        {badLink && <p role="status">Ссылка неполна или редакция отсутствует в локальной базе.</p>}
        {!visibleRows.length && rows.length > 0 && <p className="muted">Все редакции в архиве. Вы можете добавить новый пакет.</p>}
        <ul id="catalog-cards" className="catalog-grid">
          {visibleRows.map(row => <li key={row.revision}><button className="catalog-item revision-card" aria-haspopup="dialog"
            onClick={() => {
              setFollowCitation(false)
              setSelected(row.revision)
            }}>
            <span className="muted">{states[row.state]}{row.active && ' · активна'}</span>
            <strong>{row.revision}</strong>
            <span>{row.revision_date} · требований: {row.requirement_count}</span>
          </button></li>)}
        </ul>
        {!badLink && chosen && <RevisionDialog key={chosen.revision} row={chosen}
          id={followCitation ? id : null} clause={followCitation ? clause : null}
          close={() => {
            setSelected(null)
            setFollowCitation(false)
          }} deleted={() => {
            setSelected(null)
            setFollowCitation(false)
            setMessage('Редакция удалена из архива.')
            setRefresh(n => n + 1)
          }} changed={row => {
            setUpdates(current => ({ ...current, [row.revision]: row }))
            if (row.active) setActiveOverride(row.revision)
            else if (chosen.active) setActiveOverride('')
          }} />}
      </div>
    }}
  </ModulePage>
}
