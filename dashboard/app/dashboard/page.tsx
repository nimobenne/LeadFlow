'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Scissors, Play, LayoutDashboard, Download, FileSpreadsheet } from 'lucide-react'
import DaemonStatus from '@/components/DaemonStatus'
import StatsBar from '@/components/StatsBar'
import LeadTable from '@/components/LeadTable'
import { supabase } from '@/lib/supabase'
import type { Lead } from '@/lib/types'

/**
 * /dashboard page — view, filter, and export all leads.
 * Fetches leads ordered by priority_score desc on mount.
 * Subscribes to Realtime for new lead inserts.
 */
export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | null>(null)

  const loadLeads = useCallback(async () => {
    setLoading(true)
    setError(null)
    const { data, error: fetchError } = await supabase
      .from('leads')
      .select('*')
      .order('priority_score', { ascending: false, nullsFirst: false })
      .limit(5000)

    if (fetchError) {
      setError(fetchError.message)
    } else {
      setLeads((data ?? []) as Lead[])
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    loadLeads()
  }, [loadLeads])

  // Subscribe to new leads via Realtime
  useEffect(() => {
    const channel = supabase
      .channel('leads-realtime')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'leads' },
        (payload) => {
          setLeads((prev) => {
            // Insert and re-sort by priority_score desc
            const updated = [payload.new as Lead, ...prev]
            return updated.sort((a, b) => {
              const ap = a.priority_score ?? -1
              const bp = b.priority_score ?? -1
              return bp - ap
            })
          })
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [])

  /** Update a lead's outreach_status in local state after the DB write in LeadTable. */
  function handleStatusChange(id: string, status: Lead['outreach_status']) {
    setLeads((prev) =>
      prev.map((l) => (l.id === id ? { ...l, outreach_status: status } : l))
    )
  }

  async function handleExport(format: 'csv' | 'xlsx') {
    setExporting(format)
    try {
      const res = await fetch(`/api/export?format=${format}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { error?: string }).error ?? 'Export failed')
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `leadflow-leads-${new Date().toISOString().slice(0, 10)}.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Export error:', err)
      alert('Export failed. Check the console for details.')
    } finally {
      setExporting(null)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Top header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Scissors size={20} className="text-indigo-400" />
            <span className="font-bold text-lg tracking-tight text-white">LeadFlow</span>
          </div>
          <DaemonStatus />
        </div>
      </header>

      {/* Nav tabs */}
      <div className="border-b border-gray-800 bg-gray-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <nav className="flex gap-0">
            <NavTab href="/runs" active={false} label="New Run" icon={<Play size={14} />} />
            <NavTab
              href="/dashboard"
              active
              label="Dashboard"
              icon={<LayoutDashboard size={14} />}
            />
          </nav>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Stats bar */}
        {!loading && <StatsBar leads={leads} />}

        {/* Action row */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">
              {loading
                ? 'Loading leads…'
                : `${leads.length} lead${leads.length !== 1 ? 's' : ''} total`}
            </span>
            {!loading && (
              <button
                onClick={loadLeads}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Refresh
              </button>
            )}
          </div>

          {/* Export buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport('csv')}
              disabled={exporting !== null || leads.length === 0}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-700 bg-gray-800 text-gray-300 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download size={14} />
              {exporting === 'csv' ? 'Exporting…' : 'Export CSV'}
            </button>
            <button
              onClick={() => handleExport('xlsx')}
              disabled={exporting !== null || leads.length === 0}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-700 bg-gray-800 text-gray-300 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <FileSpreadsheet size={14} />
              {exporting === 'xlsx' ? 'Exporting…' : 'Export XLSX'}
            </button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="bg-red-950/50 border border-red-800 rounded-lg px-4 py-3 text-sm text-red-400">
            Failed to load leads: {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-10 bg-gray-800/50 rounded animate-pulse"
                style={{ opacity: 1 - i * 0.1 }}
              />
            ))}
          </div>
        )}

        {/* Leads table */}
        {!loading && !error && (
          <LeadTable leads={leads} onStatusChange={handleStatusChange} />
        )}
      </main>
    </div>
  )
}

function NavTab({
  href,
  active,
  label,
  icon,
}: {
  href: string
  active: boolean
  label: string
  icon: React.ReactNode
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors
        ${
          active
            ? 'border-indigo-500 text-indigo-400'
            : 'border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-600'
        }`}
    >
      {icon}
      {label}
    </Link>
  )
}
