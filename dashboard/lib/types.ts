/**
 * Core domain types for the LeadFlow dashboard.
 * These mirror the Supabase table schemas exactly.
 */

export interface Job {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  cities: string[]
  lead_limit: number
  force_refresh: boolean
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface Lead {
  id: string
  job_id: string
  stage: string
  outreach_status: 'pending' | 'contacted' | 'replied' | 'skipped'
  created_at: string
  business_name: string | null
  business_type: string | null
  city: string | null
  country: string | null
  website: string | null
  google_maps_url: string | null
  address: string | null
  phone: string | null
  instagram_url: string | null
  yell_listing_url: string | null
  booking_url: string | null
  booking_platform: string | null
  whatsapp_present: boolean | null
  has_chat_widget: boolean | null
  has_contact_form: boolean | null
  book_now_above_fold: boolean | null
  mobile_cta_strength: string | null
  services_visible: boolean | null
  pricing_visible: boolean | null
  language_detected: string | null
  decision_maker_name: string | null
  decision_maker_role: string | null
  personal_email: string | null
  generic_email: string | null
  email_source_url: string | null
  source_type: string | null
  domain: string | null
  mx_valid: boolean | null
  mailbox_status: string | null
  catch_all: boolean | null
  role_based: boolean | null
  last_verified_at: string | null
  confidence_score: number | null
  fit_score: number | null
  priority_score: number | null
  pricing_fit: string | null
  likely_missed_lead_issue: string | null
  personalization_note: string | null
  outreach_angle: string | null
  notes: string | null
}

export interface ProgressEvent {
  id: string
  job_id: string
  message: string
  stage: string | null
  business_name: string | null
  status: 'info' | 'success' | 'error'
  created_at: string
}

export interface DaemonStatus {
  id: number
  last_seen_at: string
}
