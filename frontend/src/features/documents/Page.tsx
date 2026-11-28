import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { ModulePage } from '../../shared/ModulePage'
import type { DocumentRecord } from '../../shared/contracts'

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

function FilePicker() {
  const input = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const nextId = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [picked, setPicked] = useState<{ id: number; name: string; size: number }[]>([])
  const [notice, setNotice] = useState('')

  function select(files: FileList) {
    const accepted = Array.from(files).filter((file) => /\.(pdf|docx)$/i.test(file.name))
    const entries = accepted.map((file) => ({ id: nextId.current++, name: file.name, size: file.size }))
    setPicked((previous) => [...previous, ...entries])
    setNotice(accepted.length === files.length ? '' : 'Файлы других форматов пропущены. Выберите PDF или DOCX.')
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    if (event.dataTransfer.files.length) select(event.dataTransfer.files)
  }

  return (
    <section className="file-picker scene-reveal" aria-labelledby="pick-title">
      <div className="dropzone" data-dragging={dragging}
        onDragEnter={(event) => {
          if (!event.dataTransfer.types.includes('Files')) return
          event.preventDefault()
          dragDepth.current += 1
          setDragging(true)
        }}
        onDragOver={(event) => {
          if (!event.dataTransfer.types.includes('Files')) return
          event.preventDefault()
          event.dataTransfer.dropEffect = 'copy'
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
          <p className="muted" id="pick-note">Подбор файлов без отправки на сервер.</p>
        </div>
        <input ref={input} type="file" accept=".pdf,.docx" multiple hidden aria-label="Файлы для проверки"
          onChange={(event) => {
            if (event.currentTarget.files?.length) select(event.currentTarget.files)
            event.currentTarget.value = ''
          }}
        />
        <button type="button" className="action action-primary" aria-describedby="pick-note"
          onClick={() => input.current?.click()}>
          Выбрать файлы
        </button>
      </div>
      <div role="status" aria-atomic="true">
        {notice && <p className="file-notice">{notice}</p>}
        <span className="sr-only">Выбрано файлов: {picked.length}</span>
      </div>
      {picked.length > 0 && (
        <div className="picked-files">
          <h2 className="section-title">Выбранные файлы</h2>
          <ul className="resource-list stagger-list">
            {picked.map((file) => (
              <li key={file.id} className="resource-row">
                <span className="entry-name">{file.name}</span>
                <span className="muted">{formatSize(file.size)}</span>
                <button type="button" className="text-action" aria-label={`Убрать файл ${file.name}`}
                  onClick={() => setPicked((previous) => previous.filter((item) => item.id !== file.id))}>
                  Убрать
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default function DocumentsPage({ query }: { query?: string }) {
  const documentId = new URLSearchParams(query).get('document')
  return (
    <ModulePage<DocumentRecord[]>
      title="Документы"
      description="Подберите материалы для предварительной проверки."
      path="/documents"
      sectionTitle="Документы на сервере"
      emptyTitle="Документов пока нет"
      emptyDescription="Передача файлов на сервер пока недоступна."
      beforeData={documentId ? undefined : <FilePicker />}
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
