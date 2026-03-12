'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircle, XCircle, Info, Loader2 } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import type { Job, ProgressEvent } from '@/lib/types'

interface ProgressFeedProps {
  jobId: string
}

/**
 * Live-scrolling feed of pipeline progress events for a given job.
 * Subscribes to Supabase Realtime on the `progress_events` table filtered by job_id.
 * Also polls the `jobs` table to detect when the job completes or fails.
 */
export default function ProgressFeed({ jobId }: ProgressFeedProps) {
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [jobStatus, setJobStatus] = useState<Job['status'] | null>(null)
  const [leadCount, setLeadCount] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load initial events and job status on mount
  useEffect(() => {
    async function loadInitial() {
      const [eventsRes, jobRes, leadsRes] = await Promise.all([
        supabase
          .from('progress_events')
          .select('*')
          .eq('job_id', jobId)
          .order('created_at', { ascending: true }),
        supabase
          .from('jobs')
          .select('status')
          .eq('id', jobId)
          .single(),
        supabase
          .from('leads')
          .select('id', { count: 'exact', head: true })
          .eq('job_id', jobId),
      ])

      if (eventsRes.data) setEvents(eventsRes.data as ProgressEvent[])
      if (jobRes.data) setJobStatus((jobRes.data as Pick<Job, 'status'>).status)
      if (leadsRes.count !== null) setLeadCount(leadsRes.count)
    }
    loadInitial()
  }, [jobId])

  // Subscribe to new progress events via Realtime
  useEffect(() => {
    const channel = supabase
      .channel(`progress-${jobId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'progress_events',
          filter: `job_id=eq.${jobId}`,
        },
        (payload) => {
          setEvents((prev) => [...prev, payload.new as ProgressEvent])
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'jobs',
          filter: `id=eq.${jobId}`,
        },
        (payload) => {
          const updated = payload.new as Job
          setJobStatus(updated.status)
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'leads',
          filter: `job_id=eq.${jobId}`,
        },
        () => {
          setLeadCount((n) => n + 1)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [jobId])

  // Auto-scroll to bottom on new events
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const isFinished = jobStatus === 'completed' || jobStatus === 'failed'

  return (
    <div className="space-y-3">
      {/* Status header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!isFinished && jobStatus === 'running' && (
            <Loader2 size={16} className="text-indigo-400 animate-spin" />
          )}
          <span className="text-sm font-medium text-gray-300">
            {jobStatus === 'pending' && 'Waiting to start…'}
            {jobStatus === 'running' && 'Pipeline running…'}
            {jobStatus === 'completed' && (
              <span className="text-emerald-400">Pipeline complete</span>
            )}
            {jobStatus === 'failed' && (
              <span className="text-red-400">Pipeline failed</span>
            )}
            {jobStatus === null && 'Loading…'}
          </span>
        </div>
        <span className="font-mono text-sm text-indigo-300">
          {leadCount} lead{leadCount !== 1 ? 's' : ''} found
        </span>
      </div>

      {/* Log container */}
      <div className="bg-gray-950 border border-gray-800 rounded-lg h-80 overflow-y-auto p-3 space-y-1 font-mono text-xs">
        {events.length === 0 && (
          <p className="text-gray-600 italic">Waiting for pipeline events…</p>
        )}
        {events.map((event) => (
          <EventLine key={event.id} event={event} />
        ))}

        {/* Terminal status line */}
        {jobStatus === 'completed' && (
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-800 text-emerald-400">
            <CheckCircle size={12} />
            <span>Pipeline complete — {leadCount} leads collected</span>
          </div>
        )}
        {jobStatus === 'failed' && (
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-800 text-red-400">
            <XCircle size={12} />
            <span>Pipeline failed</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function EventLine({ event }: { event: ProgressEvent }) {
  const time = new Date(event.created_at).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <div className="flex items-start gap-2 leading-relaxed">
      {/* Timestamp */}
      <span className="text-gray-600 shrink-0 w-20">{time}</span>

      {/* Icon */}
      <span className="shrink-0 mt-0.5">
        {event.status === 'success' && <CheckCircle size={11} className="text-emerald-500" />}
        {event.status === 'error' && <XCircle size={11} className="text-red-500" />}
        {event.status === 'info' && <Info size={11} className="text-blue-400" />}
      </span>

      {/* Message */}
      <span
        className={
          event.status === 'success'
            ? 'text-emerald-300'
            : event.status === 'error'
            ? 'text-red-300'
            : 'text-gray-400'
        }
      >
        {event.business_name && (
          <span className="text-gray-200 font-medium">{event.business_name} </span>
        )}
        {event.stage && (
          <span className="text-indigo-500">[{event.stage}] </span>
        )}
        {event.message}
      </span>
    </div>
  )
}
