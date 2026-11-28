import type { Evidence, Requirement } from '../../shared/contracts'

export interface Citation {
  id: string
  revision: string
  clause: string
  quote: string
}
export interface Exchange {
  question: string
  answer: string
  citations: Citation[]
  document_evidence?: Evidence[]
  document_note?: string | null
  generated?: boolean
  modelError?: string
}
export interface Thread { id: string; turns: Exchange[]; firstFilename?: string }

export const historyKey = 'fstec.dialogs.v1'
export const legacyDialog = '00000000-0000-0000-0000-000000000000'
const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i

export function readHistory(): Thread[] {
  try {
    const items = JSON.parse(localStorage.getItem(historyKey) ?? '[]')
    if (!Array.isArray(items)) return []
    return items.filter((t: Thread) => t && typeof t.id === 'string' && uuid.test(t.id) && Array.isArray(t.turns) &&
      (t.turns.length > 0 || typeof t.firstFilename === 'string') &&
      (t.firstFilename === undefined || typeof t.firstFilename === 'string') &&
      t.turns.every(m => m && typeof m.question === 'string' && typeof m.answer === 'string' &&
        (m.modelError === undefined || typeof m.modelError === 'string') &&
        (m.document_evidence === undefined || (Array.isArray(m.document_evidence) && m.document_evidence.every(item =>
          item && [item.document_id, item.filename, item.excerpt].every(s => typeof s === 'string') &&
          item.location && ['pdf_page', 'docx_section', 'unknown'].includes(item.location.kind)))) &&
        Array.isArray(m.citations) && m.citations.every(c => c && [c.id, c.revision, c.clause, c.quote].every(s => typeof s === 'string'))))
  } catch { return [] }
}

export function lookup(question: string, entries: Requirement[]): Exchange {
  const lower = question.toLocaleLowerCase('ru')
  const point = lower.match(/(?:пункт(?:а|у|е|ом)?|п\.)\s*(\d+)(?!\d)/u)?.[1]
  const terms = lower.match(/[а-яёa-z0-9-]{3,}/gu)?.filter(t =>
    !['как', 'что', 'для', 'про', 'или', 'это', 'какие', 'приказ', 'найди', 'покажи', 'требования', 'пункт'].includes(t)) ?? []
  const scored = entries.map(row => {
    const clause = row.source_reference.clause.toLocaleLowerCase('ru')
    const text = row.requirement_text.toLocaleLowerCase('ru')
    const idMatch = lower.includes(row.requirement_id.toLowerCase())
    const pointMatch = point && clause.match(/пункт\s+(\d+)/u)?.[1] === point
    const inAppendix = lower.includes('приложени')
    let score = terms.reduce((n, t) => n + (text.includes(t) ? 1 : 0), 0)
    if (point) score = pointMatch && (!inAppendix || clause.includes('приложени')) ? 100 : 0
    if (idMatch) score = 200
    return { row, score }
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score)
  const citations = scored.slice(0, 3).map(({ row }) => ({
    id: row.requirement_id, revision: row.source_reference.revision, clause: row.source_reference.clause,
    quote: row.requirement_text.length > 300 ? row.requirement_text.slice(0, 300).trimEnd() + '…' : row.requirement_text,
  }))
  return { question, citations, answer: citations.length ? 'В приказе найдены следующие пункты.'
    : 'Совпадений в приказе не найдено. Попробуйте номер пункта или точное словосочетание из документа.' }
}
