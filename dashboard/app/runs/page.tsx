'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Scissors, LayoutDashboard, Play } from 'lucide-react'
import DaemonStatus from '@/components/DaemonStatus'
import RunForm from '@/components/RunForm'
import ProgressFeed from '@/components/ProgressFeed'
import { supabase } from '@/lib/supabase'
import type { Job } from '@/lib/types'

/**
 * /runs page — configure and trigger pipeline runs, watch live progress.
 */
export default function RunsPage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [recentJobs, setRecentJobs] = useState<Job[]>([])

  // Load recent jobs on mount
  useEffect(() => {
    async function loadJobs() {
      const { data } = await supabase
        .from('jobs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(5)
      if (data) setRecentJobs(data as Job[])
    }
    loadJobs()
  }, [])

  function handleRunStarted(jobId: string) {
    setActiveJobId(jobId)
    // Prepend to recent jobs list with a pending status
    setRecentJobs((prev) => [
      {
        id: jobId,
        status: 'pending',
        cities: [],
        lead_limit: 0,
        force_refresh: false,
        created_at: new Date().toISOString(),
        started_at: null,
        completed_at: null,
      },
      ...prev.slice(0, 4),
    ])
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Top header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Scissors size={20} className="text-indigo-400" />
            <span className="font-bold text-lg tracking-tight text-white">LeadFlow</span>
          </div>
          <DaemonStatus />
        </div>
      </header>

      {/* Nav tabs */}
      <div className="border-b border-gray-800 bg-gray-950">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <nav className="flex gap-0">
            <NavTab href="/runs" active label="New Run" icon={<Play size={14} />} />
            <NavTab href="/dashboard" active={false} label="Dashboard" icon={<LayoutDashboard size={14} />} />
          </nav>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left: Run form */}
          <div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
              <h2 className="text-base font-semibold text-white mb-5">Configure Pipeline Run</h2>
              <RunForm onRunStarted={handleRunStarted} />
            </div>

            {/* Recent jobs */}
            {recentJobs.length > 0 && (
              <div className="mt-5 bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">
                  Recent Runs
                </h3>
                <div className="space-y-2">
                  {recentJobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between gap-2 py-2 border-b border-gray-800 last:border-0 cursor-pointer hover:bg-gray-800/30 rounded px-1 transition-colors"
                      onClick={() => setActiveJobId(job.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && setActiveJobId(job.id)}
                    >
                      <div className="min-w-0">
                        <p className="text-xs text-gray-300 truncate font-mono">
                          {job.id.slice(0, 8)}…
                        </p>
                        <p className="text-xs text-gray-600 mt-0.5">
                          {job.cities?.join(', ') || 'No cities'}
                        </p>
                      </div>
                      <JobStatusBadge status={job.status} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: Live feed */}
          <div>
            {activeJobId ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-white">Live Feed</h2>
                  <span className="font-mono text-xs text-gray-600">
                    job: {activeJobId.slice(0, 8)}…
                  </span>
                </div>
                <ProgressFeed jobId={activeJobId} />
              </div>
            ) : (
              <div className="bg-gray-900/50 border border-dashed border-gray-800 rounded-xl p-8 flex flex-col items-center justify-center gap-3 h-full min-h-[320px]">
                <Play size={32} className="text-gray-700" />
                <p className="text-sm text-gray-600 text-center">
                  Start a run to see live progress here.
                  <br />
                  Select a recent run on the left to reload its feed.
                </p>
              </div>
            )}
          </div>
        </div>
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

function JobStatusBadge({ status }: { status: Job['status'] }) {
  const map: Record<Job['status'], string> = {
    pending: 'text-gray-400 bg-gray-800',
    running: 'text-blue-300 bg-blue-950 animate-pulse',
    completed: 'text-emerald-300 bg-emerald-950',
    failed: 'text-red-300 bg-red-950',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${map[status]}`}>
      {status}
    </span>
  )
}
