'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

type RunStatus = 'idle' | 'running' | 'completed' | 'failed'

/**
 * Shows the status of the most recent pipeline job from Supabase.
 * Polls every 15 seconds.
 */
export default function DaemonStatus() {
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [lastRun, setLastRun] = useState<string | null>(null)

  async function checkStatus() {
    const { data } = await supabase
      .from('jobs')
      .select('status, created_at')
      .order('created_at', { ascending: false })
      .limit(1)
      .single()

    if (!data) {
      setStatus('idle')
      return
    }

    setStatus(data.status as RunStatus)
    setLastRun(data.created_at)
  }

  useEffect(() => {
    checkStatus()
    const interval = setInterval(checkStatus, 15_000)
    return () => clearInterval(interval)
  }, [])

  if (status === null) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span className="inline-block w-2 h-2 rounded-full bg-gray-600 animate-pulse" />
        Loading…
      </div>
    )
  }

  if (status === 'idle') {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span className="inline-block w-2 h-2 rounded-full bg-gray-600" />
        No runs yet
      </div>
    )
  }

  if (status === 'running') {
    return (
      <div className="flex items-center gap-2 text-sm text-indigo-400">
        <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 animate-pulse shadow-[0_0_6px_#818cf8]" />
        Pipeline running…
      </div>
    )
  }

  if (status === 'completed') {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-400">
        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
        Last run complete
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 text-sm text-red-400">
      <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
      Last run failed
    </div>
  )
}
