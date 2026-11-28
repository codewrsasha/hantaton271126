import { useState } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import { useApi } from '../../shared/api'
import type { Requirement, RequirementRevision } from '../../shared/contracts'
import './styles.css'

const states = { draft: 'Черновик', published: 'Опубликована', archived: 'В архиве' }
const revisionsPath = '/requirements/revisions'

function Entries({ revision, id, clause }: { revision: string; id: string | null; clause: string | null }) {
  const result = useApi<Requirement[]>(`${revisionsPath}/${encodeURIComponent(revision)}/requirements`)
  if (result.state === 'loading') return <p role="status">Загрузка требований…</p>
  if (result.state === 'error') return <p role="alert">Не удалось загрузить требования редакции.</p>
  const visible = id ? result.data.filter(r => r.requirement_id === id && r.source_reference.clause === clause) : result.data
  if (!visible.length) return <p role="status">{id ? 'Требование по этой ссылке не найдено.' : 'В выбранной редакции нет требований.'}</p>
  return <ul className="resource-list">{visible.map(r => <li key={r.requirement_id} className="catalog-entry">
    <div><strong>Пункт {r.source_reference.clause}</strong><p className="muted">{r.requirement_id}</p></div>
    <p className="normative-text">{r.requirement_text}</p>
  </li>)}</ul>
}

export default function RequirementsPage({ query }: { query?: string }) {
  const [refresh, setRefresh] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [selected, setSelected] = useState('')
  const params = new URLSearchParams(query)
  const id = params.get('requirement'), revision = params.get('revision'), clause = params.get('clause')
  const citation = params.has('requirement') || params.has('clause')
  const invalid = (citation && (!id || !clause || !revision)) || (params.has('revision') && !revision)
    || ['requirement', 'revision', 'clause'].some(key => params.getAll(key).length > 1)

  async function write(path: string, success: string, body?: File) {
    setBusy(true)
    setMessage('Сохранение…')
    try {
      const response = await fetch('/api/v1' + path, { method: 'POST', body,
        headers: { 'X-Catalog-Action': '1', ...(body ? { 'Content-Type': 'application/json' } : {}) } })
      const data = await response.json()
      if (!response.ok) {
        setMessage(typeof data.detail === 'string' ? data.detail : 'Сервер отклонил операцию.')
        return
      }
      setSelected(data.revision)
      setMessage(body && response.status === 200 ? 'Этот пакет уже импортирован.' : success)
      setRefresh(n => n + 1)
    } catch {
      setMessage('Не удалось получить ответ локального сервера. Обновите каталог для проверки результата.')
    } finally { setBusy(false) }
  }

  return <ModulePage<RequirementRevision[]> title="База требований" description="Приказ ФСТЭК России № 117."
    path={revisionsPath} refresh={refresh} sectionTitle="Редакции" emptyTitle="База требований пока пуста"
    emptyDescription="Выберите локальный JSON-пакет для первого импорта." beforeData={<>
      <form className="catalog-form" onSubmit={e => {
        e.preventDefault()
        if (file && !busy) {
          if (file.size > 4 * 1024 * 1024) setMessage('Размер пакета превышает 4 МиБ.')
          else void write(revisionsPath, 'Пакет импортирован как черновик.', file)
        }
      }}>
        <label htmlFor="catalog-file">Пакет редакции · JSON до 4 МиБ</label>
        <input id="catalog-file" type="file" accept=".json,application/json" disabled={busy}
          onChange={e => setFile(e.target.files?.[0] ?? null)} />
        <button className="action" disabled={!file || busy}>Импортировать</button>
      </form>
      <p role="status">{message}</p>
    </>}>
    {rows => {
      const active = rows.find(r => r.active)
      const chosen = rows.find(r => r.revision === (revision ?? (selected || active?.revision || rows[0]?.revision)))
      const badLink = invalid || (revision !== null && !chosen)
      if (!rows.length && !badLink) return null
      const action = (operation: string, question: string, success: string) => {
        if (chosen && window.confirm(question + ' Редакция: ' + chosen.revision + '.'))
          void write(`${revisionsPath}/${encodeURIComponent(chosen.revision)}/${operation}`, success)
      }
      return <div className="revision-catalog">
        <p>Активная редакция: <strong>{active?.revision ?? 'не выбрана'}</strong></p>
        {!!rows.length && <div className="filter"><label htmlFor="revision">Просмотр редакции</label>
          <select id="revision" value={chosen?.revision ?? ''} disabled={busy} onChange={e => {
            window.location.hash = 'requirements?revision=' + encodeURIComponent(e.target.value)
          }}>
            {!chosen && <option value="">Выберите редакцию</option>}
            {rows.map(r => <option key={r.revision} value={r.revision}>
              {r.revision} · {r.revision_date} · {states[r.state]} · требований: {r.requirement_count} · {r.source}
            </option>)}
          </select></div>}
        {(citation || badLink) && <a className="text-action" href="#requirements">К каталогу редакций</a>}
        {badLink ? <p role="status">Ссылка неполна или редакция отсутствует в локальной базе.</p> : chosen && <>
          <h3>Редакция {chosen.revision}</h3>
          <dl className="revision-meta">
            <dt>Состояние</dt><dd>{states[chosen.state]}{chosen.active && ' · активна'}</dd>
            <dt>Дата редакции</dt><dd>{chosen.revision_date}</dd>
            <dt>Источник</dt><dd>{chosen.source}</dd>
            <dt>Дата получения</dt><dd>{chosen.obtained_on}</dd>
            <dt>Импорт</dt><dd>{new Date(chosen.imported_at).toLocaleString('ru-RU')}</dd>
            <dt>SHA-256 пакета</dt><dd><code>{chosen.sha256}</code></dd>
            <dt>Сверка с источником</dt><dd>{chosen.reviewed_at
              ? 'Пользователь подтвердил сверку ' + new Date(chosen.reviewed_at).toLocaleString('ru-RU')
              : 'Ручная сверка не подтверждена'}</dd>
          </dl>
          <div className="catalog-actions">
            {chosen.state === 'draft' && <button disabled={busy} className="action" onClick={() =>
              action('publish', 'Вы сверили текст каждого пункта и реквизиты с официальным источником и подтверждаете публикацию?', 'Сверка зафиксирована. Редакция опубликована.')}>Подтвердить сверку и опубликовать</button>}
            {chosen.state === 'published' && !chosen.active && <button disabled={busy} className="action" onClick={() =>
              action('activate', 'Использовать эту редакцию для новых проверок?', 'Активная редакция выбрана.')}>Сделать активной</button>}
            {chosen.active && <button disabled={busy} className="action" onClick={() =>
              action('deactivate', 'Снять редакцию с активного использования?', 'Редакция снята с использования.')}>Снять с использования</button>}
            {!chosen.active && chosen.state !== 'archived' && <button disabled={busy} className="action" onClick={() =>
              action('archive', 'Перенести редакцию в архив без возможности повторной публикации?', 'Редакция в архиве.')}>Архивировать</button>}
          </div>
          <h3>Нормативный текст · {chosen.requirement_count}</h3>
          <Entries key={chosen.revision} revision={chosen.revision} id={id} clause={clause} />
        </>}
      </div>
    }}
  </ModulePage>
}
