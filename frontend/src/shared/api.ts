import { useEffect, useState } from 'react'

export async function getApi<T>(path: string, signal?: AbortSignal, dialogId?: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    signal,
    headers: dialogId ? { 'X-Dialog-Id': dialogId } : undefined,
    cache: dialogId ? 'no-store' : undefined,
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

export async function saveApi<T>(path: string, method: 'POST' | 'PUT' | 'DELETE', data?: object, dialogId?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json', 'X-Inspector-Action': '1',
        ...(dialogId ? { 'X-Dialog-Id': dialogId } : {}),
      },
      body: JSON.stringify(data),
    })
  } catch {
    throw new Error('Не удалось связаться с локальным сервером.')
  }
  if (response.status === 204) return undefined as T
  if (response.ok) return response.json() as Promise<T>
  const body = await response.json().catch(() => null) as { detail?: unknown } | null
  throw new Error(typeof body?.detail === 'string' ? body.detail : 'Локальный сервер не выполнил операцию.')
}

type RequestState<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'error' }

export function useApi<T>(path: string | null, refresh: string | number = 0, dialogId?: string): RequestState<T> {
  const [result, setResult] = useState<{ path: string; dialogId?: string; value: RequestState<T> }>()

  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    setResult({ path, dialogId, value: { state: 'loading' } })
    getApi<T>(path, controller.signal, dialogId)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ path, dialogId, value: { state: 'ready', data } })
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ path, dialogId, value: { state: 'error' } })
      })
    return () => controller.abort()
  }, [path, refresh, dialogId])

  return result && result.path === path && result.dialogId === dialogId ? result.value : { state: 'loading' }
}
