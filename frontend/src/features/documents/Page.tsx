import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import { useApi } from '../../shared/api'
import type { DocumentRecord, DocumentUploadLimits } from '../../shared/contracts'
import { uploadDocument } from './upload'
import './styles.css'

const states: Record<DocumentRecord['state'], string> = {
  received: 'Получен',
  extracted: 'Текст извлечён',
  needs_review: 'Требуется проверка',
  failed: 'Ошибка обработки',
}

const sizeFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 })
function formatSize(bytes: number) {
  if (bytes >= 1024 ** 2) return `${sizeFormat.format(bytes / 1024 ** 2)} МБ`
  if (bytes >= 1024) return `${sizeFormat.format(bytes / 1024)} КБ`
  return `${sizeFormat.format(bytes)} Б`
}

type PickedFile = { id: number; file: File; error?: string }

function selectionError(file: File, limit: number | undefined) {
  if (file.size === 0) return 'Файл пуст.'
  if (limit !== undefined && file.size > limit) return `Размер превышает предел ${formatSize(limit)}.`
  return null
}

function FilePicker({ onStored }: { onStored: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const nextId = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [picked, setPicked] = useState<PickedFile[]>([])
  const [notice, setNotice] = useState('')
  const [activeId, setActiveId] = useState<number | null>(null)
  const limits = useApi<DocumentUploadLimits>('/documents/limits')
  const maxBytes = limits.state === 'ready' ? limits.data.max_size_bytes : undefined
  const eligible = picked.filter(({ file }) => !selectionError(file, maxBytes))
  const busy = activeId !== null

  function select(files: FileList) {
    const entries = Array.from(files, (file) => ({ id: nextId.current++, file }))
    setPicked((previous) => [...previous, ...entries])
    setNotice('')
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    if (!busy && event.dataTransfer.files.length) select(event.dataTransfer.files)
  }

  async function submit() {
    if (busy || !eligible.length) return
    setDragging(false)
    dragDepth.current = 0
    setNotice('')
    setPicked((previous) => previous.map((item) => ({ ...item, error: undefined })))

    let stored = 0
    for (const { id, file } of eligible) {
      setActiveId(id)
      try {
        await uploadDocument(file)
        stored += 1
        setPicked((previous) => previous.filter((item) => item.id !== id))
        onStored()
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Не удалось загрузить файл.'
        setPicked((previous) => previous.map((item) => item.id === id ? { ...item, error: message } : item))
      }
    }
    setActiveId(null)
    const failed = eligible.length - stored
    setNotice(`Сохранено файлов: ${stored}.${failed ? ` Не удалось загрузить: ${failed}.` : ''}`)
  }

  return (
    <section className="file-picker scene-reveal" aria-labelledby="pick-title">
      <div className="dropzone" data-dragging={dragging}
        onDragEnter={(event) => {
          if (!event.dataTransfer.types.includes('Files')) return
          event.preventDefault()
          if (busy) return
          dragDepth.current += 1
          setDragging(true)
        }}
        onDragOver={(event) => {
          if (!event.dataTransfer.types.includes('Files')) return
          event.preventDefault()
          event.dataTransfer.dropEffect = busy ? 'none' : 'copy'
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1)
          if (!dragDepth.current) setDragging(false)
        }}
        onDrop={handleDrop}
      >
        <div>
          <p className="eyebrow">PDF / DOCX</p>
          <h2 id="pick-title">Перетащите файлы сюда</h2>
          <p className="muted" id="pick-note">
            {maxBytes !== undefined
              ? `До ${formatSize(maxBytes)} на файл. Для PDF-сканов распознавание текста недоступно.`
              : 'Допустимый размер проверяет сервер. Поддерживаются PDF и DOCX.'}
          </p>
        </div>
        <input ref={input} type="file" accept=".pdf,.docx" multiple hidden disabled={busy}
          aria-label="Файлы для проверки"
          onChange={(event) => {
            if (event.currentTarget.files?.length) select(event.currentTarget.files)
            event.currentTarget.value = ''
          }}
        />
        <button type="button" className="action action-document-secondary" aria-describedby="pick-note"
          disabled={busy} onClick={() => input.current?.click()}>
          Выбрать файлы
        </button>
      </div>

      {picked.length > 0 && (
        <div className="picked-files">
          <div className="upload-heading">
            <h2 className="section-title">Выбранные файлы</h2>
            <button type="button" className="action action-primary" onClick={submit}
              disabled={busy || !eligible.length}>
              {busy ? 'Загрузка…' : 'Загрузить файлы'}
            </button>
          </div>
          <ul className="resource-list">
            {picked.map(({ id, file, error }) => {
              const problem = selectionError(file, maxBytes) ?? error
              return (
                <li key={id} className="resource-row">
                  <span className="entry-name">{file.name}</span>
                  <span className="muted">{formatSize(file.size)}</span>
                  <button type="button" className="text-action" aria-label={`Убрать файл ${file.name}`}
                    disabled={busy} onClick={() => setPicked((previous) => previous.filter((item) => item.id !== id))}>
                    Убрать
                  </button>
                  {activeId === id && <p className="upload-note muted">Передача и извлечение текста…</p>}
                  {problem && <p className="upload-note">{problem}</p>}
                </li>
              )
            })}
          </ul>
        </div>
      )}
      <div role="status" aria-atomic="true">
        {busy && <p className="file-notice">Файл передаётся на локальный сервер и обрабатывается…</p>}
        {notice && <p className="file-notice">{notice}</p>}
      </div>
    </section>
  )
}

export default function DocumentsPage({ query }: { query?: string }) {
  const documentId = new URLSearchParams(query).get('document')
  const [refresh, setRefresh] = useState(0)
  return (
    <ModulePage<DocumentRecord[]>
      hideHeading title="Документы"
      description="Загрузите материалы для предварительной проверки."
      path="/documents"
      refresh={refresh}
      sectionTitle="Загруженные файлы"
      emptyTitle="Документов пока нет"
      emptyDescription="Выберите и загрузите PDF или DOCX, чтобы извлечь текст."
      beforeData={documentId ? undefined : <FilePicker onStored={() => setRefresh((value) => value + 1)} />}
    >
      {(documents) => {
        if (!documents.length && !documentId) return null
        const visible = documentId ? documents.filter((doc) => doc.id === documentId) : documents
        return (
          <>
            {documentId && <p className="source-navigation"><a className="text-action" href="#documents">Все документы</a></p>}
            {visible.length ? (
              <ul className="resource-list stagger-list">
                {visible.map((doc) => (
                  <li key={doc.id} className="resource-row">
                    <span className="entry-name">{doc.filename}</span>
                    <span className="muted">{doc.format.toUpperCase()} · {formatSize(doc.size_bytes)}</span>
                    <span className="state-label">{states[doc.state]}</span>
                    {doc.issue && <p className="upload-note muted">{doc.issue.message}</p>}
                  </li>
                ))}
              </ul>
            ) : <p className="module-state">Документ не найден на сервере.</p>}
          </>
        )
      }}
    </ModulePage>
  )
}
