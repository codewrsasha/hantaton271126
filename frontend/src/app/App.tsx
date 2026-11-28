import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { RequirementsOverlay } from '../features/requirements/Page'
import { historyKey, lookup, readHistory } from '../features/chat/history'
import { uploadDocument } from '../features/documents/upload'
import { useApi } from '../shared/api'
import type { DocumentRecord, Health, Requirement, RequirementRevision } from '../shared/contracts'

function subscribe(update: () => void) {
  window.addEventListener('hashchange', update)
  return () => window.removeEventListener('hashchange', update)
}
const getHash = () => window.location.hash.slice(1)

export default function App() {
  const hash = useSyncExternalStore(subscribe, getHash)
  const [route, query] = hash.split('?')
  const [threads, setThreads] = useState(readHistory)
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [opened, setOpened] = useState<DocumentRecord | null>(null)
  const [uploadMessage, setUploadMessage] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [storageError, setStorageError] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const stream = useRef<HTMLDivElement>(null)
  const catalogTrigger = useRef<HTMLButtonElement>(null)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const health = useApi<Health>('/health')
  const entries = useApi<Requirement[]>('/requirements')
  const documents = useApi<DocumentRecord[]>('/documents', refresh)
  const fragments = useApi<{text: string}[]>(opened ? '/documents/' + opened.id + '/fragments' : '/documents/none/fragments')
  const metadata = useApi<RequirementRevision>('/requirements/active')
  const thread = threads.find(t => t.id === selected)
  const legacyCatalog = route === 'requirements'
  const starter = ['Пункт 1', 'Управление доступом', 'Классы защищенности']
  const canSend = entries.state === 'ready'

  useEffect(() => {
    if (stream.current) stream.current.scrollTop = stream.current.scrollHeight
  }, [thread])
  useEffect(() => {
    try { localStorage.setItem(historyKey, JSON.stringify(threads)); setStorageError(false) }
    catch { setStorageError(true) }
  }, [threads])
  useEffect(() => { setHistoryOpen(false) }, [hash])

  function openChat(id: string | null) {
    setSelected(id)
    setDraft('')
    setHistoryOpen(false)
    window.location.hash = 'chat'
    requestAnimationFrame(() => input.current?.focus())
  }

  function send(raw: string) {
    const question = raw.trim()
    if (!question || entries.state !== 'ready') return
    const turn = lookup(question, entries.data)
    const id = thread?.id ?? crypto.randomUUID()
    const updated = { id, turns: [...(thread?.turns ?? []), turn] }
    setThreads(previous => [updated, ...previous.filter(t => t.id !== id)])
    setSelected(id)
    setDraft('')
    input.current?.focus()
  }
  function closeCatalog() {
    if (legacyCatalog) window.location.hash = 'chat'
    setCatalogOpen(false)
    requestAnimationFrame(() => catalogTrigger.current?.focus())
  }

  async function addFiles(files: FileList) {
    setUploadMessage('Загрузка файлов…')
    for (const file of Array.from(files)) {
      try { await uploadDocument(file); setRefresh(v => v + 1); setUploadMessage('Файл загружен.') }
      catch (error) { setUploadMessage(error instanceof Error ? error.message : 'Ошибка загрузки.') }
    }
  }

  return <div className={'studio' + (opened ? ' has-document workspace-active' : '')}>
    <header className="studio-bar">
      <a className="wordmark" href="#chat" aria-label="Инспектор ФСТЭК, к чату"><span className="brand-tile" aria-hidden="true">И</span>Инспектор<span className="brand-spec">ФСТЭК</span></a>
      <div className="mobile-controls"><button className="quiet-button" onClick={() => setHistoryOpen(!historyOpen)} aria-expanded={historyOpen}>История</button>
        {opened && <button className="quiet-button" onClick={() => setOpened(null)}>В чат</button>}</div>
      <div className="online" role="status" data-ready={health.state === 'ready'}><i />{health.state === 'ready' ? 'Локальный сервер' : health.state === 'loading' ? 'Подключение…' : 'Сервер недоступен'}</div>
    </header>

    <aside className={'history-rail' + (historyOpen ? ' expanded' : '')} aria-label="История чатов">
      <button className="new-chat" onClick={() => openChat(null)}><span aria-hidden="true">＋</span> Новый чат</button>
      <h2 className="panel-label">История чатов</h2>
      <div className="history-scroll">{threads.length ? threads.map(t => <button key={t.id} aria-current={t.id === selected ? 'true' : undefined}
        className="thread-link" title={t.turns[0].question} onClick={() => openChat(t.id)}>{t.turns[0].question}</button>)
        : <p className="rail-empty">Здесь появятся ваши диалоги.</p>}</div>
      <button ref={catalogTrigger} type="button" className="source-card" aria-haspopup="dialog" onClick={() => { setHistoryOpen(false); setCatalogOpen(true) }}>
        <span className="book-cover" aria-hidden="true">117</span><span><small>Нормативная база</small><strong>Приказ ФСТЭК № 117</strong>
        <small>{metadata.state === 'ready' ? 'Пунктов: ' + metadata.data.requirement_count : 'Каталог требований'} · Для чтения</small></span></button>
    </aside>

    <main className="conversation" aria-label="Чат по приказу">
      <div className="conversation-bar"><span>Ассистент</span><span className="mode-chip">Поиск по приказу</span></div>
      <div ref={stream} className={'message-stream' + (!thread ? ' is-empty' : '')} aria-live="polite">
        {!thread ? <div className="welcome">
          <div className="order-monogram" aria-hidden="true">§</div>
          <h1>Что найдём<br/>в приказе?</h1>
          <p>Введите номер пункта или тему. Инспектор найдёт фрагменты приказа № 117 и покажет источник.</p>
          <div className="suggestions">{starter.map(s => <button key={s} disabled={!canSend} onClick={() => send(s)}>{s}</button>)}</div>
        </div> : <div className="transcript">{thread.turns.map((turn, index) => <div key={index} className="exchange">
          <p className="user-message">{turn.question}</p>
          <div className="response"><strong>Инспектор</strong><p>{turn.answer}</p>
            {turn.citations.map(c => <div className="citation" key={c.id}><a href={'#requirements?' + new URLSearchParams({ requirement: c.id, revision: c.revision, clause: c.clause })}>{c.clause} ↗</a>
              <blockquote>{c.quote}</blockquote><small>{c.id} · Ред. {c.revision}</small></div>)}</div>
        </div>)}</div>}
      </div>
      {documents.state === 'ready' && documents.data.length > 0 && <div className="chat-files" aria-label="Загруженные файлы"><span>Файлы</span>{documents.data.map(doc => <button key={doc.id} onClick={() => setOpened(doc)}>{doc.filename}</button>)}</div>}
      <div className="composer-area"><form className="composer" onSubmit={e => { e.preventDefault(); send(draft) }}>
        <textarea ref={input} rows={2} value={draft} aria-label="Сообщение" placeholder="Спросите о требованиях приказа…"
          onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault(); send(draft)
          } }}/>
        <div className="compose-actions"><div><input ref={fileInput} hidden type="file" multiple accept=".pdf,.docx" onChange={e => { if (e.target.files?.length) void addFiles(e.target.files); e.target.value = '' }} />
          <button type="button" className="attach-file" onClick={() => fileInput.current?.click()}>＋ Добавить файл</button><span> PDF / DOCX</span></div>
          <button type="submit" aria-label="Отправить сообщение" title="Отправить сообщение" disabled={!draft.trim() || !canSend}>↑</button></div>
      </form><p className="compose-note" role="status">{uploadMessage || (storageError ? 'Историю не удалось сохранить в браузере.' : entries.state === 'error' ? 'Каталог недоступен. Проверьте соединение с сервером.' : 'Локальный поиск по тексту · Языковая модель не подключена')}</p></div>
    </main>

    {opened && <aside className="workspace document-view" aria-label="Открытый документ">
      <header><h2>{opened.filename}</h2><button className="quiet-button" onClick={() => setOpened(null)}>Закрыть</button></header>
      <p className="muted">{opened.format.toUpperCase()} · {opened.state === 'extracted' ? 'Текст извлечён' : 'Требуется проверка'}</p>
      {opened.issue && <p>{opened.issue.message}</p>}
      {fragments.state === 'loading' && <p>Загрузка текста…</p>}
      {fragments.state === 'error' && <p>Не удалось открыть текст документа.</p>}
      {fragments.state === 'ready' && (fragments.data.length ? fragments.data.map((part, i) => <p className="document-fragment" key={i}>{part.text}</p>) : <p>Текст документа не извлечён.</p>)}
    </aside>}
    {(catalogOpen || legacyCatalog) && <RequirementsOverlay key={hash} query={legacyCatalog ? query : undefined} close={closeCatalog}/>}
  </div>
}
