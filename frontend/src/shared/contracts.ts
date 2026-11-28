export interface Health {
  status: 'ok'
  database: 'sqlite'
}

export interface DashboardSummary {
  documents: number
  requirements: number
  analyses: number
  reports: number
}

export interface DocumentRecord {
  id: string
  filename: string
  format: 'pdf' | 'docx'
  size_bytes: number
  state: 'received' | 'extracted' | 'needs_review' | 'failed'
  issue: {
    code: 'no_text' | 'partial_extraction' | 'extraction_failed' | 'unknown_location'
    message: string
  } | null
}

export interface DocumentUploadLimits {
  max_size_bytes: number
}

export interface Requirement {
  requirement_id: string
  requirement_text: string
  source_reference: {
    order_number: '117'
    revision: string
    clause: string
  }
}

export interface RequirementRevision {
  order_number: '117'
  revision: string
  revision_date: string
  obtained_on: string
  source: string
  sha256: string
  requirement_count: number
}

export type Location =
  | { kind: 'pdf_page'; page: number }
  | { kind: 'docx_section'; section: string }
  | { kind: 'unknown' }

export type EvidenceRelation = 'supports' | 'contradicts' | 'context'

export interface Evidence {
  document_id: string
  filename: string
  excerpt: string
  location: Location
  relation: EvidenceRelation
}

export type ComplianceStatus =
  | 'соответствует'
  | 'частично соответствует'
  | 'не соответствует'
  | 'недостаточно данных'
  | 'требуется проверка'

export interface ExpertReview {
  comment: string
  corrected_status?: ComplianceStatus | null
  evidence_relations?: Record<number, EvidenceRelation>
}

export interface AnalysisResult extends Requirement {
  status: ComplianceStatus
  evidence: Evidence[]
  explanation: string
  confidence?: number | null
  review?: ExpertReview | null
}

export interface AnalysisRun {
  id: string
  document_ids: string[]
  state: 'queued' | 'running' | 'completed' | 'failed'
  results: AnalysisResult[]
  revision: string
  source: string
  revision_sha256: string
  revision_date: string
  obtained_on: string
  created_at: string
  documents: (DocumentRecord & { fragment_count: number })[]
  error: string | null
}

export interface Report {
  id: string
  analysis_id: string
  filename: string
}

export interface ChatStatus {
  state: 'unavailable' | 'ready'
}
