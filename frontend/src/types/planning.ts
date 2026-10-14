import type { DayDetail } from './index'

export interface Violation {
  code: string
  severity: 'error' | 'warning'
  message: string
  day_index?: number | null
  subject?: string | null
}

export interface ValidationReport {
  valid: boolean
  violations: Violation[]
  total_cost: number
  pricing_status: string
  day_minutes: Record<number, number>
  poi_verifiable_rate: number
}

export interface EditProposal {
  proposal_id: string
  draft_id: string
  status: 'pending' | 'blocked' | 'applied' | 'cancelled'
  before: Record<number, DayDetail>
  after: Record<number, DayDetail>
  validation_before: ValidationReport
  validation_after: ValidationReport
  changes: string[]
  rounds: number
  message: string
  run_id?: string
}

export interface PlanningConstraints {
  must_visit: string[]
  max_day_minutes: number
  budget: number | null
  day_end_time: string
}
