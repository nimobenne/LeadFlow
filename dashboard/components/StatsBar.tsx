'use client'

import type { Lead } from '@/lib/types'

interface StatsBarProps {
  leads: Lead[]
}

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: string
}

function StatCard({ label, value, sub, accent = 'text-white' }: StatCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 min-w-0">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide truncate">{label}</p>
      <p className={`font-mono text-2xl font-bold mt-1 ${accent}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  )
}

/**
 * Horizontal card bar displaying aggregate metrics over the provided leads array.
 * Re-computes whenever the leads array reference changes (e.g. after filter or Realtime update).
 */
export default function StatsBar({ leads }: StatsBarProps) {
  const total = leads.length

  const tierA = leads.filter((l) => l.fit_score !== null && l.fit_score >= 80).length
  const tierB = leads.filter(
    (l) => l.fit_score !== null && l.fit_score >= 65 && l.fit_score < 80
  ).length
  const tierC = leads.filter(
    (l) => l.fit_score !== null && l.fit_score >= 50 && l.fit_score < 65
  ).length

  const scored = leads.filter((l) => l.priority_score !== null)
  const avgPriority =
    scored.length > 0
      ? Math.round(scored.reduce((sum, l) => sum + (l.priority_score ?? 0), 0) / scored.length)
      : null

  const hasEmail = leads.filter(
    (l) => l.personal_email !== null || l.generic_email !== null
  ).length
  const hasEmailPct = total > 0 ? Math.round((hasEmail / total) * 100) : 0

  const hasChatWidget = leads.filter((l) => l.has_chat_widget === true).length
  const hasChatPct = total > 0 ? Math.round((hasChatWidget / total) * 100) : 0

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
      <StatCard label="Total Leads" value={total} />
      <StatCard
        label="Tier A"
        value={tierA}
        sub="fit ≥ 80"
        accent="text-emerald-400"
      />
      <StatCard
        label="Tier B"
        value={tierB}
        sub="fit 65–79"
        accent="text-yellow-400"
      />
      <StatCard
        label="Tier C"
        value={tierC}
        sub="fit 50–64"
        accent="text-orange-400"
      />
      <StatCard
        label="Avg Priority"
        value={avgPriority ?? '—'}
        sub="scored leads"
        accent="text-indigo-400"
      />
      <StatCard
        label="Has Email"
        value={`${hasEmailPct}%`}
        sub={`${hasEmail} leads`}
        accent="text-blue-400"
      />
      <StatCard
        label="Has Chat"
        value={`${hasChatPct}%`}
        sub={`${hasChatWidget} leads`}
        accent="text-purple-400"
      />
    </div>
  )
}
