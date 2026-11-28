import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { RequirementsOverlay } from '../features/requirements/Page'
import { historyKey, legacyDialog, lookup, readHistory } from '../features/chat/history'
import type { Exchange } from '../features/chat/history'
import { uploadDocument } from '../features/documents/upload'
import { saveApi, useApi } from '../shared/api'
import type { ChatStatus, DocumentRecord, Health, Location, Requirement, RequirementRevision } from '../shared/contracts'

function subscribe(update: () => void) {
  window.addEventListener('hashchange', update)
  return () => window.removeEventListener('hashchange', update)
}
const getHash = () => window.location.hash.slice(1)

function locationLabel(location: Location) {
  if (location.kind === 'pdf_page') return 'Страница ' + location.page
  if (location.kind === 'docx_section') return 'Раздел ' + location.section
  return 'Точное место неизвестно'
}

export default function App() {
  const hash = useSyncExternalStore(subscribe, getHash)
  const [route, query] = hash.split('?')
  const [threads, setThreads] = useState(readHistory)
  const [selected, setSelected] = useState<string>(() => crypto.randomUUID())
  const activeDialog = useRef(selected)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<{ id: string; question: string } | null>(null)
  const generating = useRef(false)
  const [statusRefresh, setStatusRefresh] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [archiveRefresh, setArchiveRefresh] = useState(0)
  const [opened, setOpened] = useState<DocumentRecord | null>(null)
  const [questionDocument, setQuestionDocument] = useState<DocumentRecord | null>(null)
  const [uploadMessage, setUploadMessage] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  const uploading = useRef(new Set<string>())
  const fileInput = useRef<HTMLInputElement>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [storageError, setStorageError] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const stream = useRef<HTMLDivElement>(null)
  const catalogTrigger = useRef<HTMLButtonElement>(null)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const health = useApi<Health>('/health')
  const model = useApi<ChatStatus>('/chat/status', statusRefresh)
  const entries = useApi<Requirement[]>('/requirements')
  const documents = useApi<DocumentRecord[]>('/documents', refresh, selected)
  const archived = useApi<DocumentRecord[]>('/documents', archiveRefresh, legacyDialog)
  const fragments = useApi<{text: string}[]>(opened && '/documents/' + opened.id + '/fragments', 0, selected)
  const metadata = useApi<RequirementRevision>('/requirements/active')
  const thread = threads.find(t => t.id === selected)
  const turns = thread?.turns ?? []
  const history = archived.state === 'ready' && archived.data.length && !threads.some(t => t.id === legacyDialog)
    ? [...threads, { id: legacyDialog, turns: [], firstFilename: archived.data[0].filename }]
    : threads
  const legacyCatalog = route === 'requirements'
  const hasFiles = documents.state === 'ready' && documents.data.length > 0
  const starter = hasFiles ? ['Кратко перескажи документ', 'Пункт 1'] : ['Пункт 1', 'Управление доступом', 'Классы защищенности']
  const canSend = !pending && deleting !== selected
  const waiting = pending?.id === selected ? pending.question : null

  useEffect(() => {
    if (stream.current) stream.current.scrollTop = stream.current.scrollHeight
  }, [thread, waiting])
  useEffect(() => {
    try { localStorage.setItem(historyKey, JSON.stringify(threads)); setStorageError(false) }
    catch { setStorageError(true) }
  }, [threads])
  useEffect(() => { setHistoryOpen(false) }, [hash])

  function openChat(id: string = crypto.randomUUID()) {
    activeDialog.current = id
    setSelected(id)
    setDraft('')
    setOpened(null)
    setQuestionDocument(null)
    setUploadMessage('')
    setHistoryOpen(false)
    window.location.hash = 'chat'
    requestAnimationFrame(() => input.current?.focus())
  }

  async function deleteChat(id: string, title: string) {
    if (deleting) return
    if (pending?.id === id || uploading.current.has(id)) {
      setHistoryError('Дождитесь завершения ответа или загрузки файлов перед удалением.')
      return
    }
    if (!window.confirm(`Удалить «${title}»? Диалог, его файлы, проверки и отчёты будут удалены из приложения.`)) return
    setHistoryError('')
    setDeleting(id)
    try {
      await saveApi<void>(`/chat/dialogs/${id}`, 'DELETE')
      setThreads(previous => previous.filter(thread => thread.id !== id))
      if (id === legacyDialog) setArchiveRefresh(value => value + 1)
      if (activeDialog.current === id) {
        openChat()
      } else {
        requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.new-chat')?.focus())
      }
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Не удалось удалить диалог.')
    } finally {
      setDeleting(null)
    }
  }

  async function send(raw: string) {
    const question = raw.trim()
    if (!question || generating.current || deleting === selected) return
    const id = selected
    const history = turns.slice(-3).map(turn => ({ question: turn.question.slice(0, 250), answer: turn.answer.slice(0, 400) }))
    generating.current = true
    setPending({ id, question })
    setDraft('')
    input.current?.focus()
    let turn: Exchange
    try {
      turn = await saveApi<Exchange>('/chat/messages', 'POST', { question, history, document_id: questionDocument?.id }, id)
    } catch (error) {
      turn = !questionDocument && entries.state === 'ready' ? lookup(question, entries.data) : { question, answer: '', citations: [] }
      turn.modelError = error instanceof Error ? error.message : 'Не удалось получить ответ модели.'
    } finally {
      generating.current = false
      setPending(null)
      setStatusRefresh(value => value + 1)
    }
    setThreads(previous => {
      const current = previous.find(t => t.id === id)
      return [{ ...current, id, turns: [...(current?.turns ?? []), turn] }, ...previous.filter(t => t.id !== id)]
    })
  }
  function closeCatalog() {
    if (legacyCatalog) window.location.hash = 'chat'
    setCatalogOpen(false)
    requestAnimationFrame(() => catalogTrigger.current?.focus())
  }

  async function addFiles(files: FileList) {
    const dialogId = selected
    if (deleting === dialogId || uploading.current.has(dialogId)) return
    uploading.current.add(dialogId)
    const batch = Array.from(files)
    const errors: string[] = []
    setUploadMessage('Загрузка файлов…')
    for (const file of batch) {
      try {
        const uploaded = await uploadDocument(file, dialogId)
        setThreads(previous => previous.some(t => t.id === dialogId)
          ? previous
          : [{ id: dialogId, turns: [], firstFilename: uploaded.filename }, ...previous])
        if (activeDialog.current === dialogId) setRefresh(v => v + 1)
      } catch (error) {
        errors.push(file.name + ': ' + (error instanceof Error ? error.message : 'Ошибка загрузки.'))
      }
    }
    uploading.current.delete(dialogId)
    if (activeDialog.current === dialogId) {
      setUploadMessage(errors.length ? errors.join(' ') : batch.length === 1 ? 'Файл загружен.' : 'Файлы загружены.')
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
      <button className="new-chat" onClick={() => openChat()}><span aria-hidden="true">＋</span> Новый чат</button>
      <h2 className="panel-label">История чатов</h2>
      {historyError && <p className="rail-empty" role="alert">{historyError}</p>}
      <div className="history-scroll">{history.length ? history.map(t => {
        const title = t.id === legacyDialog ? 'Ранее загруженные файлы' : t.turns[0]?.question ?? t.firstFilename ?? 'Диалог'
        return <div className="history-row" key={t.id}>
          <button aria-current={t.id === selected ? 'true' : undefined} disabled={deleting === t.id}
            className="thread-link" title={title} onClick={() => openChat(t.id)}>{title}</button>
          <button type="button" className="thread-delete" title="Удалить диалог" aria-label={`Удалить диалог «${title}»`}
            disabled={deleting !== null} onClick={() => void deleteChat(t.id, title)}>×</button>
        </div>
      })
        : <p className="rail-empty">Здесь появятся ваши диалоги.</p>}</div>
      <button ref={catalogTrigger} type="button" className="source-card" aria-haspopup="dialog" onClick={() => { setHistoryOpen(false); setCatalogOpen(true) }}>
        <span className="book-cover" aria-hidden="true">117</span><span><small>Нормативная база</small><strong>Приказ ФСТЭК № 117</strong>
        <small>{metadata.state === 'ready' ? 'Пунктов: ' + metadata.data.requirement_count : 'Каталог требований'} · Для чтения</small></span></button>
    </aside>

    <main className="conversation" aria-label="Чат по приказу">
      <div className="conversation-bar"><span>Ассистент</span><span className="mode-chip">
        {model.state === 'ready' && model.data.state === 'ready' ? 'Локальная модель · Qwen3 4B' : 'Поиск по приказу'}
      </span></div>
      <div ref={stream} className={'message-stream' + (!turns.length && !waiting ? ' is-empty' : '')} aria-live="polite">
        {!turns.length && !waiting ? <div className="welcome">
          <div className="order-monogram" aria-hidden="true">§</div>
          <h1>Что найдём<br/>в приказе?</h1>
          <p>Задайте вопрос о приказе № 117 или приложите документ. Инспектор покажет найденные источники.</p>
          <div className="suggestions">{starter.map(s => <button key={s} disabled={!canSend} onClick={() => send(s)}>{s}</button>)}</div>
        </div> : <div className="transcript">{turns.map((turn, index) => <div key={index} className="exchange">
          <p className="user-message">{turn.question}</p>
          <div className="response"><strong>{turn.generated === false ? 'Инспектор' : turn.document_evidence ? 'Инспектор · Qwen3 4B' : 'Поиск по приказу'}</strong>
            {turn.modelError && <p>{turn.modelError}</p>}
            {turn.answer && <p className="chat-answer">{turn.answer}</p>}
            {turn.document_note && <p className="muted">{turn.document_note}</p>}
            {turn.citations.map((c, i) => <div className="citation" key={c.id}><a href={'#requirements?' + new URLSearchParams({ requirement: c.id, revision: c.revision, clause: c.clause })}>{turn.document_evidence ? `[Н${i + 1}] ` : ''}{c.clause}</a>
              <blockquote>{c.quote}</blockquote><small>{c.id} · Ред. {c.revision}</small></div>)}
            {turn.document_evidence?.map((item, i) => {
              const doc = documents.state === 'ready' ? documents.data.find(doc => doc.id === item.document_id) : undefined
              return <div className="citation" key={i}>
                <button type="button" className="quiet-button" disabled={!doc} onClick={() => doc && setOpened(doc)}>[Д{i + 1}] {item.filename}</button>
                <blockquote>{item.excerpt}</blockquote><small>{locationLabel(item.location)}</small>
              </div>
            })}</div>
        </div>)}{waiting && <div className="exchange"><p className="user-message">{waiting}</p>
          <div className="response" role="status">Модель готовит ответ…</div></div>}</div>}
      </div>
      {documents.state === 'ready' && documents.data.length > 0 && <div className="chat-files" aria-label="Загруженные файлы"><span>Файлы</span>{documents.data.map(doc => <button key={doc.id} onClick={() => setOpened(doc)}>{doc.filename}</button>)}</div>}
      <div className="composer-area"><form className="composer" onSubmit={e => { e.preventDefault(); send(draft) }}>
        {questionDocument && <div className="question-document"><span>Вопрос о файле: {questionDocument.filename}</span>
          <button type="button" className="quiet-button" onClick={() => { setQuestionDocument(null); input.current?.focus() }}>Снять выбор</button>
        </div>}
        <textarea ref={input} rows={2} maxLength={1500} value={draft} aria-label="Сообщение"
          placeholder={questionDocument ? 'Спросите о содержании файла…' : 'Спросите о приказе или приложенном файле…'}
          onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault(); send(draft)
          } }}/>
        <div className="compose-actions"><div><input ref={fileInput} hidden type="file" multiple accept=".pdf,.docx" onChange={e => { if (e.target.files?.length) void addFiles(e.target.files); e.target.value = '' }} />
          <button type="button" className="attach-file" disabled={deleting === selected} onClick={() => fileInput.current?.click()}>＋ Добавить файл</button><span> PDF / DOCX</span></div>
          <button type="submit" aria-label="Отправить сообщение" title="Отправить сообщение" disabled={!draft.trim() || !canSend}>↑</button></div>
      </form><p className="compose-note" role="status">{uploadMessage || (storageError ? 'Историю не удалось сохранить в браузере.' : documents.state === 'error' ? 'Не удалось загрузить список файлов диалога.' : pending && !waiting ? 'Модель отвечает в другом диалоге.' : model.state === 'ready' && model.data.state === 'unavailable' ? 'Модель недоступна. Работает локальный поиск по приказу.' : 'Ответы и документы обрабатываются локально.')}</p></div>
    </main>

    {opened && <aside className="workspace document-view" aria-label="Открытый документ">
      <header><h2>{opened.filename}</h2><button className="quiet-button" onClick={() => setOpened(null)}>Закрыть</button></header>
      <p className="muted">{opened.format.toUpperCase()} · {opened.state === 'extracted' ? 'Текст извлечён' : 'Требуется проверка'}</p>
      <button type="button" className="quiet-button" onClick={() => {
        setQuestionDocument(opened)
        setOpened(null)
        requestAnimationFrame(() => input.current?.focus())
      }}>Спросить о файле</button>
      {opened.issue && <p>{opened.issue.message}</p>}
      {fragments.state === 'loading' && <p>Загрузка текста…</p>}
      {fragments.state === 'error' && <p>Не удалось открыть текст документа.</p>}
      {fragments.state === 'ready' && (fragments.data.length ? fragments.data.map((part, i) => <p className="document-fragment" key={i}>{part.text}</p>) : <p>Текст документа не извлечён.</p>)}
    </aside>}
    {(catalogOpen || legacyCatalog) && <RequirementsOverlay key={hash} query={legacyCatalog ? query : undefined} close={closeCatalog}/>}
  </div>
}
