import { useEffect, useRef, useState } from 'react'
import { useApi } from '../../shared/api'
import type { Requirement, RequirementRevision } from '../../shared/contracts'

export function RequirementsOverlay({ query, close }: { query?: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const entries = useApi<Requirement[]>('/requirements')
  const metadata = useApi<RequirementRevision>('/requirements/active')
  const params = new URLSearchParams(query)
  const linkedId = params.get('requirement')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(linkedId)
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    const node = dialog.current
    node?.showModal()
    return () => node?.close()
  }, [])

  const rows = entries.state === 'ready' ? entries.data.filter(row => {
    const src = row.source_reference
    if (!showAll && linkedId && (row.requirement_id !== linkedId ||
      (params.has('revision') && params.get('revision') !== src.revision) ||
      (params.has('clause') && params.get('clause') !== src.clause))) return false
    const text = [src.clause, row.requirement_id, row.requirement_text].join(' ').toLocaleLowerCase('ru')
    return text.includes(search.trim().toLocaleLowerCase('ru'))
  }) : []

  return <dialog className="source-dialog" ref={dialog} aria-labelledby="source-title"
    onCancel={e => { e.preventDefault(); close() }} onClick={e => { if (e.target === dialog.current) close() }}>
    <div className="source-inner">
      <header><div><p className="panel-label">База требований</p><h2 id="source-title">Приказ ФСТЭК № 117</h2></div>
        <button type="button" className="quiet-button" onClick={close}>Закрыть</button></header>
      {metadata.state === 'ready' && <details className="source-meta"><summary>Редакция {metadata.data.revision_date} · Пунктов: {metadata.data.requirement_count}</summary>
        <p>{metadata.data.source}</p><p>Дата получения: {metadata.data.obtained_on}</p><p>SHA-256 JSON: {metadata.data.sha256}</p></details>}
      {linkedId && !showAll ? <button className="quiet-button" onClick={() => setShowAll(true)}>Все пункты приказа</button>
        : <input className="source-search" type="search" aria-label="Поиск по приказу" placeholder="Номер пункта, слово или фраза" value={search} onChange={e => setSearch(e.target.value)} />}
      <div className="source-list">
        {entries.state === 'loading' && <p role="status">Загрузка приказа…</p>}
        {(entries.state === 'error' || metadata.state === 'error') && <p role="alert">Не удалось получить данные каталога.</p>}
        {entries.state === 'ready' && !rows.length && <p>{linkedId && !showAll ? 'Требование по этой ссылке не найдено.' : 'По вашему запросу пунктов не найдено.'}</p>}
        {rows.map(row => <article key={row.requirement_id}><button className="source-row" aria-expanded={expanded === row.requirement_id}
          onClick={() => setExpanded(expanded === row.requirement_id ? null : row.requirement_id)}>
          <span><small>{row.requirement_id}</small>{row.source_reference.clause}</span><span aria-hidden="true">{expanded === row.requirement_id ? '−' : '+'}</span>
        </button>{expanded === row.requirement_id && <p className="clause-text">{row.requirement_text}</p>}</article>)}
      </div>
    </div>
  </dialog>
}
