import { useEffect, useState } from 'react'

export async function getApi<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { signal })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
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
