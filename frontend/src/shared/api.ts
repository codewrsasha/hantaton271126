import { useEffect, useState } from 'react'

export async function getApi<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { signal })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

export async function saveApi<T>(path: string, method: 'POST' | 'PUT', data: object): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-Inspector-Action': '1' },
      body: JSON.stringify(data),
    })
  } catch {
    throw new Error('Не удалось связаться с локальным сервером.')
  }
  if (response.ok) return response.json() as Promise<T>
  const body = await response.json().catch(() => null) as { detail?: unknown } | null
  throw new Error(typeof body?.detail === 'string' ? body.detail : 'Локальный сервер не выполнил операцию.')
}

type RequestState<T> =
  | { state: 'loading' }
  | { state: 'ready'; data: T }
  | { state: 'error' }

export function useApi<T>(path: string, refresh: string | number = 0) {
  const [result, setResult] = useState<RequestState<T>>({ state: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    setResult({ state: 'loading' })
    getApi<T>(path, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setResult({ state: 'ready', data })
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ state: 'error' })
      })
    return () => controller.abort()
  }, [path, refresh])

  return result
}
