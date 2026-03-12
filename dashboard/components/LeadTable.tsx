'use client'

import { useState, useMemo } from 'react'
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  Mail,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
} from 'lucide-react'
import { supabase } from '@/lib/supabase'
import ScoreBadge from './ScoreBadge'
import type { Lead } from '@/lib/types'

const PAGE_SIZE = 50

type SortKey = keyof Lead
type SortDir = 'asc' | 'desc'

type OutreachStatus = Lead['outreach_status']

const OUTREACH_OPTIONS: OutreachStatus[] = ['pending', 'contacted', 'replied', 'skipped']

const OUTREACH_COLORS: Record<OutreachStatus, string> = {
  pending: 'text-gray-400 bg-gray-800 border-gray-700',
  contacted: 'text-blue-300 bg-blue-950 border-blue-800',
  replied: 'text-emerald-300 bg-emerald-950 border-emerald-800',
  skipped: 'text-gray-600 bg-gray-900 border-gray-800',
}

interface LeadTableProps {
  leads: Lead[]
  onStatusChange: (id: string, status: OutreachStatus) => void
}

/**
 * Sortable, filterable, paginated table of leads.
 * Outreach status updates are written directly to Supabase on change.
 */
export default function LeadTable({ leads, onStatusChange }: LeadTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('priority_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(1)
  const [fitTier, setFitTier] = useState<'all' | 'A' | 'B' | 'C'>('all')
  const [selectedCities, setSelectedCities] = useState<string[]>([])
  const [selectedStatuses, setSelectedStatuses] = useState<OutreachStatus[]>([])
  const [search, setSearch] = useState('')
  const [updatingIds, setUpdatingIds] = useState<Set<string>>(new Set())
  const [tooltip, setTooltip] = useState<{ id: string; text: string } | null>(null)

  // Derive unique city list from leads
  const cities = useMemo(() => {
    const set = new Set(leads.map((l) => l.city).filter(Boolean) as string[])
    return Array.from(set).sort()
  }, [leads])

  // Filter
  const filtered = useMemo(() => {
    return leads.filter((lead) => {
      if (fitTier !== 'all') {
        const fs = lead.fit_score
        if (fitTier === 'A' && (fs === null || fs < 80)) return false
        if (fitTier === 'B' && (fs === null || fs < 65 || fs >= 80)) return false
        if (fitTier === 'C' && (fs === null || fs < 50 || fs >= 65)) return false
      }
      if (selectedCities.length > 0 && !selectedCities.includes(lead.city ?? '')) return false
      if (selectedStatuses.length > 0 && !selectedStatuses.includes(lead.outreach_status))
        return false
      if (search.trim()) {
        const q = search.trim().toLowerCase()
        if (!lead.business_name?.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [leads, fitTier, selectedCities, selectedStatuses, search])

  // Sort
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      if (typeof av === 'number' && typeof bv === 'number') {
        return sortDir === 'asc' ? av - bv : bv - av
      }
      const as = String(av).toLowerCase()
      const bs = String(bv).toLowerCase()
      if (as < bs) return sortDir === 'asc' ? -1 : 1
      if (as > bs) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [filtered, sortKey, sortDir])

  // Paginate
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
    setPage(1)
  }

  async function handleStatusChange(id: string, status: OutreachStatus) {
    setUpdatingIds((s) => new Set(s).add(id))
    const { error } = await supabase
      .from('leads')
      .update({ outreach_status: status })
      .eq('id', id)
    setUpdatingIds((s) => {
      const next = new Set(s)
      next.delete(id)
      return next
    })
    if (!error) {
      onStatusChange(id, status)
    }
  }

  function toggleCity(city: string) {
    setSelectedCities((prev) =>
      prev.includes(city) ? prev.filter((c) => c !== city) : [...prev, city]
    )
    setPage(1)
  }

  function toggleStatus(status: OutreachStatus) {
    setSelectedStatuses((prev) =>
      prev.includes(status) ? prev.filter((s) => s !== status) : [...prev, status]
    )
    setPage(1)
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (col !== sortKey) return <ArrowUpDown size={12} className="text-gray-600" />
    return sortDir === 'asc' ? (
      <ArrowUp size={12} className="text-indigo-400" />
    ) : (
      <ArrowDown size={12} className="text-indigo-400" />
    )
  }

  function Th({
    label,
    col,
    className = '',
  }: {
    label: string
    col: SortKey
    className?: string
  }) {
    return (
      <th
        className={`px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-300 select-none whitespace-nowrap ${className}`}
        onClick={() => handleSort(col)}
      >
        <span className="inline-flex items-center gap-1">
          {label}
          <SortIcon col={col} />
        </span>
      </th>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Search */}
        <input
          type="text"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          placeholder="Search business name…"
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-600 w-52"
        />

        {/* Fit tier */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700">
          {(['all', 'A', 'B', 'C'] as const).map((tier) => (
            <button
              key={tier}
              type="button"
              onClick={() => {
                setFitTier(tier)
                setPage(1)
              }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors
                ${
                  fitTier === tier
                    ? tier === 'A'
                      ? 'bg-emerald-700 text-emerald-100'
                      : tier === 'B'
                      ? 'bg-yellow-700 text-yellow-100'
                      : tier === 'C'
                      ? 'bg-orange-700 text-orange-100'
                      : 'bg-indigo-700 text-indigo-100'
                    : 'bg-gray-900 text-gray-400 hover:bg-gray-800'
                }`}
            >
              {tier === 'all' ? 'All' : `Tier ${tier}`}
            </button>
          ))}
        </div>

        {/* City filter */}
        {cities.length > 0 && (
          <select
            multiple
            value={selectedCities}
            onChange={(e) => {
              const vals = Array.from(e.target.selectedOptions).map((o) => o.value)
              setSelectedCities(vals)
              setPage(1)
            }}
            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-600 max-h-9"
            title="Filter by city (hold Ctrl/Cmd for multi)"
          >
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}

        {/* Outreach status filter */}
        <div className="flex gap-1">
          {OUTREACH_OPTIONS.map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => toggleStatus(status)}
              className={`px-2.5 py-1 text-xs rounded-full border transition-colors capitalize
                ${
                  selectedStatuses.includes(status)
                    ? OUTREACH_COLORS[status]
                    : 'bg-gray-900 text-gray-500 border-gray-700 hover:border-gray-500'
                }`}
            >
              {status}
            </button>
          ))}
        </div>

        {/* Result count */}
        <span className="ml-auto text-xs text-gray-600 font-mono">
          {filtered.length} result{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-sm text-left border-collapse">
          <thead className="bg-gray-900 border-b border-gray-800">
            <tr>
              <Th label="Business" col="business_name" className="min-w-[180px]" />
              <Th label="City" col="city" />
              <Th label="Fit" col="fit_score" />
              <Th label="Conf" col="confidence_score" />
              <Th label="Priority" col="priority_score" />
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">
                Email
              </th>
              <Th label="Phone" col="phone" />
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">
                Chat
              </th>
              <Th label="Booking" col="booking_platform" />
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide min-w-[160px]">
                Note
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">
                Yell
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap min-w-[130px]">
                Outreach
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {paginated.length === 0 && (
              <tr>
                <td colSpan={12} className="px-3 py-8 text-center text-gray-600 text-sm">
                  No leads match the current filters.
                </td>
              </tr>
            )}
            {paginated.map((lead) => (
              <tr
                key={lead.id}
                className="hover:bg-gray-900/50 transition-colors group"
              >
                {/* Business name */}
                <td className="px-3 py-2.5 max-w-[220px]">
                  {lead.website ? (
                    <a
                      href={lead.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-400 hover:text-indigo-300 font-medium truncate block"
                      title={lead.business_name ?? undefined}
                    >
                      {lead.business_name ?? '—'}
                    </a>
                  ) : (
                    <span className="text-gray-300 font-medium truncate block" title={lead.business_name ?? undefined}>
                      {lead.business_name ?? '—'}
                    </span>
                  )}
                  {lead.business_type && (
                    <span className="text-xs text-gray-600 truncate block">{lead.business_type}</span>
                  )}
                </td>

                {/* City */}
                <td className="px-3 py-2.5 text-gray-400 whitespace-nowrap">
                  {lead.city ?? '—'}
                </td>

                {/* Scores */}
                <td className="px-3 py-2.5">
                  <ScoreBadge score={lead.fit_score} type="fit" />
                </td>
                <td className="px-3 py-2.5">
                  <ScoreBadge score={lead.confidence_score} type="confidence" />
                </td>
                <td className="px-3 py-2.5">
                  <ScoreBadge score={lead.priority_score} type="priority" />
                </td>

                {/* Email */}
                <td className="px-3 py-2.5">
                  {lead.personal_email || lead.generic_email ? (
                    <div className="flex items-center gap-1.5">
                      <Mail
                        size={13}
                        className={
                          lead.personal_email ? 'text-emerald-400' : 'text-gray-500'
                        }
                      />
                      <span
                        className="font-mono text-xs text-gray-300 truncate max-w-[140px]"
                        title={lead.personal_email ?? lead.generic_email ?? undefined}
                      >
                        {lead.personal_email ?? lead.generic_email}
                      </span>
                    </div>
                  ) : (
                    <span className="text-gray-700">—</span>
                  )}
                </td>

                {/* Phone */}
                <td className="px-3 py-2.5 font-mono text-xs text-gray-400 whitespace-nowrap">
                  {lead.phone ?? '—'}
                </td>

                {/* Has chat widget */}
                <td className="px-3 py-2.5 text-center">
                  {lead.has_chat_widget === true ? (
                    <Check size={14} className="text-emerald-500 mx-auto" />
                  ) : lead.has_chat_widget === false ? (
                    <X size={14} className="text-gray-700 mx-auto" />
                  ) : (
                    <span className="text-gray-700">—</span>
                  )}
                </td>

                {/* Booking platform */}
                <td className="px-3 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                  {lead.booking_platform ? (
                    lead.booking_url ? (
                      <a
                        href={lead.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300"
                      >
                        {lead.booking_platform}
                      </a>
                    ) : (
                      lead.booking_platform
                    )
                  ) : (
                    <span className="text-gray-700">—</span>
                  )}
                </td>

                {/* Personalization note */}
                <td className="px-3 py-2.5 max-w-[180px] relative">
                  {lead.personalization_note ? (
                    <div
                      className="relative"
                      onMouseEnter={() =>
                        setTooltip({ id: lead.id, text: lead.personalization_note! })
                      }
                      onMouseLeave={() => setTooltip(null)}
                    >
                      <span className="text-xs text-gray-400 truncate block cursor-default">
                        {lead.personalization_note}
                      </span>
                      {tooltip?.id === lead.id && (
                        <div className="absolute bottom-full left-0 z-50 mb-1.5 w-72 bg-gray-800 border border-gray-700 rounded-lg p-2.5 text-xs text-gray-200 shadow-xl pointer-events-none">
                          {tooltip.text}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-700">—</span>
                  )}
                </td>

                {/* Yell listing */}
                <td className="px-3 py-2.5 text-center">
                  {lead.yell_listing_url ? (
                    <a
                      href={lead.yell_listing_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-indigo-400 transition-colors inline-flex justify-center"
                      title="View Yell listing"
                    >
                      <ExternalLink size={13} />
                    </a>
                  ) : (
                    <span className="text-gray-700">—</span>
                  )}
                </td>

                {/* Outreach status inline dropdown */}
                <td className="px-3 py-2.5">
                  <select
                    value={lead.outreach_status}
                    disabled={updatingIds.has(lead.id)}
                    onChange={(e) =>
                      handleStatusChange(lead.id, e.target.value as OutreachStatus)
                    }
                    className={`text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-600 transition-colors cursor-pointer disabled:opacity-50
                      ${OUTREACH_COLORS[lead.outreach_status]} bg-transparent`}
                  >
                    {OUTREACH_OPTIONS.map((s) => (
                      <option key={s} value={s} className="bg-gray-900 text-gray-200">
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-gray-600 font-mono">
            Page {page} of {totalPages} · {sorted.length} total
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            {/* Page number buttons — show up to 7 */}
            {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
              let p: number
              if (totalPages <= 7) {
                p = i + 1
              } else if (page <= 4) {
                p = i + 1
              } else if (page >= totalPages - 3) {
                p = totalPages - 6 + i
              } else {
                p = page - 3 + i
              }
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 text-xs rounded border transition-colors
                    ${
                      p === page
                        ? 'bg-indigo-700 border-indigo-600 text-white'
                        : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                    }`}
                >
                  {p}
                </button>
              )
            })}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
