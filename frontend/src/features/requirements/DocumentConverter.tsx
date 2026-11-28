import { useState } from 'react'
import type { FormEvent } from 'react'

interface DraftMetadata {
  order_number: string
  revision: string
  revision_date: string
  obtained_on: string
  source: string
}

export interface Conversion {
  package: DraftMetadata & { requirements: unknown[] }
  warnings: string[]
}

export function DocumentConverter({ disabled, draft, filename, save, discard }: {
  disabled: boolean
  draft: Conversion
  filename: string
  save: (file: File) => Promise<void>
  discard: () => void
}) {
  const { requirements, ...fields } = draft.package
  const [metadata, setMetadata] = useState(fields)
  const [entries, setEntries] = useState(() => JSON.stringify(requirements, null, 2))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function serialize() {
    let requirements: unknown
    try {
      requirements = JSON.parse(entries)
    } catch {
      throw new Error('Исправьте синтаксис JSON в поле «Требования».')
    }
    if (!Array.isArray(requirements) || !requirements.length) throw new Error('Добавьте хотя бы одно требование в массив JSON.')
    return new File([JSON.stringify({ ...metadata, requirements }, null, 2)],
      `${metadata.revision || 'requirements'}.json`, { type: 'application/json' })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await save(serialize())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось сохранить черновик.')
    } finally {
      setBusy(false)
    }
  }

  return <div className="catalog-converter">
    {error && <p role="alert">{error}</p>}
    <form className="catalog-converter" onSubmit={submit}>
      <h3>Черновик · {filename}</h3>
      <p className="muted">Сверьте распознанные пункты и текст с оригиналом. Заполните даты и уточните источник.</p>
      {!!draft.warnings.length && <ul className="catalog-errors">{draft.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>}
      <fieldset disabled={busy || disabled}>
        <label>Идентификатор редакции<input required maxLength={96} pattern="[A-Za-z0-9][A-Za-z0-9._\x2d]*"
          value={metadata.revision} onChange={event => setMetadata({ ...metadata, revision: event.target.value })} /></label>
        <label>Дата редакции<input type="date" required value={metadata.revision_date}
          onChange={event => setMetadata({ ...metadata, revision_date: event.target.value })} /></label>
        <label>Дата получения<input type="date" required value={metadata.obtained_on}
          onChange={event => setMetadata({ ...metadata, obtained_on: event.target.value })} /></label>
        <label>Источник<input required maxLength={512} value={metadata.source}
          onChange={event => setMetadata({ ...metadata, source: event.target.value })} /></label>
        <label>Требования (JSON)<textarea rows={12} value={entries} spellCheck={false}
          onChange={event => setEntries(event.target.value)} /></label>
      </fieldset>
      <div className="catalog-actions">
        <button type="button" className="action catalog-button" disabled={busy} onClick={discard}>Пропустить черновик</button>
        <button type="button" className="action catalog-button" disabled={busy} onClick={event => {
          if (!event.currentTarget.form?.reportValidity()) return
          try {
            const file = serialize()
            const url = URL.createObjectURL(file)
            const link = document.createElement('a')
            link.href = url
            link.download = file.name
            link.click()
            window.setTimeout(() => URL.revokeObjectURL(url), 1000)
            setError('')
          } catch (cause) {
            setError(cause instanceof Error ? cause.message : 'Не удалось подготовить JSON.')
          }
        }}>Скачать JSON</button>
        <button className="action action-primary catalog-button" disabled={busy || disabled}>Добавить как черновик</button>
      </div>
    </form>
  </div>
}
