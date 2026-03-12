import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import * as XLSX from 'xlsx'
import type { Lead } from '@/lib/types'

/**
 * GET /api/export
 *
 * Query params:
 *   format         csv | xlsx          (required)
 *   fit_tier       A | B | C           (optional)
 *   city           comma-separated     (optional)
 *   outreach_status comma-separated    (optional)
 *   job_id         UUID                (optional)
 *
 * Returns a downloadable file of filtered leads.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl

  const format = searchParams.get('format')
  if (format !== 'csv' && format !== 'xlsx') {
    return NextResponse.json(
      { error: 'format must be "csv" or "xlsx"' },
      { status: 400 }
    )
  }

  const fitTier = searchParams.get('fit_tier')
  const cityParam = searchParams.get('city')
  const outreachParam = searchParams.get('outreach_status')
  const jobId = searchParams.get('job_id')

  // Build Supabase server-side client (still uses anon key for v1 — no RLS)
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  let query = supabase
    .from('leads')
    .select('*')
    .order('priority_score', { ascending: false, nullsFirst: false })

  if (jobId) {
    query = query.eq('job_id', jobId)
  }

  if (cityParam) {
    const cities = cityParam.split(',').map((c) => c.trim()).filter(Boolean)
    if (cities.length > 0) {
      query = query.in('city', cities)
    }
  }

  if (outreachParam) {
    const statuses = outreachParam.split(',').map((s) => s.trim()).filter(Boolean)
    if (statuses.length > 0) {
      query = query.in('outreach_status', statuses)
    }
  }

  const { data, error } = await query.limit(10_000)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  let leads = (data ?? []) as Lead[]

  // Apply fit_tier filter in-process (computed field)
  if (fitTier === 'A') {
    leads = leads.filter((l) => l.fit_score !== null && l.fit_score >= 80)
  } else if (fitTier === 'B') {
    leads = leads.filter(
      (l) => l.fit_score !== null && l.fit_score >= 65 && l.fit_score < 80
    )
  } else if (fitTier === 'C') {
    leads = leads.filter(
      (l) => l.fit_score !== null && l.fit_score >= 50 && l.fit_score < 65
    )
  }

  const filename = `leadflow-leads-${new Date().toISOString().slice(0, 10)}`

  if (format === 'csv') {
    const csv = buildCsv(leads)
    return new NextResponse(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}.csv"`,
      },
    })
  }

  // XLSX
  const buffer = buildXlsx(leads)
  return new NextResponse(buffer, {
    status: 200,
    headers: {
      'Content-Type':
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'Content-Disposition': `attachment; filename="${filename}.xlsx"`,
    },
  })
}

// ---------------------------------------------------------------------------
// Column definitions — controls export order and header labels
// ---------------------------------------------------------------------------

const EXPORT_COLUMNS: { key: keyof Lead; label: string }[] = [
  { key: 'business_name', label: 'Business Name' },
  { key: 'business_type', label: 'Business Type' },
  { key: 'city', label: 'City' },
  { key: 'country', label: 'Country' },
  { key: 'website', label: 'Website' },
  { key: 'phone', label: 'Phone' },
  { key: 'address', label: 'Address' },
  { key: 'personal_email', label: 'Personal Email' },
  { key: 'generic_email', label: 'Generic Email' },
  { key: 'decision_maker_name', label: 'Decision Maker' },
  { key: 'decision_maker_role', label: 'Role' },
  { key: 'fit_score', label: 'Fit Score' },
  { key: 'confidence_score', label: 'Confidence Score' },
  { key: 'priority_score', label: 'Priority Score' },
  { key: 'pricing_fit', label: 'Pricing Fit' },
  { key: 'outreach_status', label: 'Outreach Status' },
  { key: 'outreach_angle', label: 'Outreach Angle' },
  { key: 'personalization_note', label: 'Personalization Note' },
  { key: 'booking_platform', label: 'Booking Platform' },
  { key: 'booking_url', label: 'Booking URL' },
  { key: 'has_chat_widget', label: 'Has Chat Widget' },
  { key: 'whatsapp_present', label: 'WhatsApp' },
  { key: 'has_contact_form', label: 'Has Contact Form' },
  { key: 'book_now_above_fold', label: 'Book Now Above Fold' },
  { key: 'mobile_cta_strength', label: 'Mobile CTA Strength' },
  { key: 'services_visible', label: 'Services Visible' },
  { key: 'pricing_visible', label: 'Pricing Visible' },
  { key: 'instagram_url', label: 'Instagram' },
  { key: 'yell_listing_url', label: 'Yell Listing' },
  { key: 'google_maps_url', label: 'Google Maps' },
  { key: 'domain', label: 'Domain' },
  { key: 'mx_valid', label: 'MX Valid' },
  { key: 'mailbox_status', label: 'Mailbox Status' },
  { key: 'catch_all', label: 'Catch All' },
  { key: 'role_based', label: 'Role Based' },
  { key: 'likely_missed_lead_issue', label: 'Missed Lead Issue' },
  { key: 'notes', label: 'Notes' },
  { key: 'stage', label: 'Stage' },
  { key: 'job_id', label: 'Job ID' },
  { key: 'created_at', label: 'Created At' },
]

// ---------------------------------------------------------------------------
// CSV builder — manually escapes values; no external dep
// ---------------------------------------------------------------------------

function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return ''
  const str = String(value)
  // Wrap in quotes if contains comma, newline, or double-quote
  if (str.includes('"') || str.includes(',') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function buildCsv(leads: Lead[]): string {
  const header = EXPORT_COLUMNS.map((c) => csvEscape(c.label)).join(',')
  const rows = leads.map((lead) =>
    EXPORT_COLUMNS.map((c) => csvEscape(lead[c.key])).join(',')
  )
  return [header, ...rows].join('\r\n')
}

// ---------------------------------------------------------------------------
// XLSX builder using the xlsx package
// ---------------------------------------------------------------------------

function buildXlsx(leads: Lead[]): ArrayBuffer {
  const headers = EXPORT_COLUMNS.map((c) => c.label)

  const rows = leads.map((lead) =>
    EXPORT_COLUMNS.map((c) => {
      const v = lead[c.key]
      if (v === null || v === undefined) return ''
      if (typeof v === 'boolean') return v ? 'Yes' : 'No'
      return v
    })
  )

  const worksheetData = [headers, ...rows]
  const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

  // Bold header row
  const range = XLSX.utils.decode_range(worksheet['!ref'] ?? 'A1')
  for (let col = range.s.c; col <= range.e.c; col++) {
    const cellAddr = XLSX.utils.encode_cell({ r: 0, c: col })
    if (!worksheet[cellAddr]) continue
    worksheet[cellAddr].s = { font: { bold: true } }
  }

  // Auto-fit column widths (approximate)
  worksheet['!cols'] = headers.map((h, colIdx) => {
    const maxLen = Math.max(
      h.length,
      ...rows.map((row) => String(row[colIdx] ?? '').length)
    )
    return { wch: Math.min(maxLen + 2, 60) }
  })

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Leads')

  return XLSX.write(workbook, { type: 'array', bookType: 'xlsx' }) as ArrayBuffer
}
