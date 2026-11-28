import type { DocumentRecord } from '../../shared/contracts'

export async function uploadDocument(file: File, dialogId?: string): Promise<DocumentRecord> {
  const form = new FormData()
  form.append('file', file)
  let response: Response
  try {
    response = await fetch('/api/v1/documents', {
      method: 'POST',
      body: form,
      headers: dialogId ? { 'X-Dialog-Id': dialogId } : undefined,
    })
  } catch {
    throw new Error('Не удалось связаться с локальным сервером. Проверьте, запущен ли он.')
  }
  if (response.ok) return response.json() as Promise<DocumentRecord>
  const error = await response.json().catch(() => null) as { detail?: unknown } | null
  throw new Error(typeof error?.detail === 'string' ? error.detail : 'Не удалось загрузить файл.')
}
