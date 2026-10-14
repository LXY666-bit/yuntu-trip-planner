export interface ReservationInfo {
  status: 'required' | 'not_required' | 'unknown' | 'conflicting'
  advance_days?: number | null
  release_time?: string | null
  channel?: string
  tips?: string
  evidence?: string
  source_url?: string | null
  source_title?: string
  captured_at?: string | null
}

export interface ReservationFields {
  reservation?: ReservationInfo
  reservation_required?: boolean | null
  reservation_tips?: string
  reservation_booked_for?: string | null
}

export interface ReservationTask {
  id: string
  name: string
  visit_date: string
  day_index: number
  status: 'booked' | 'past_visit' | 'unknown' | 'conflicting' | 'not_required' | 'needs_check' | 'upcoming' | 'due'
  booked: boolean
  reservation: ReservationInfo
  remind_at: string | null
  default_reminder_time: boolean
  calendar_eligible: boolean
}
