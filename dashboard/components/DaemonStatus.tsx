'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { DaemonStatus as DaemonStatusType } from '@/lib/types'

/**
 * Polls the `daemon_status` table every 15 seconds.
 * Shows a green indicator if the daemon checked in within the last 60 seconds,
 * or a red indicator with instructions if it is stale or missing.
 */
export default function DaemonStatus() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [lastSeen, setLastSeen] = useState<string | null>(null)

  async function checkStatus() {
    const { data, error } = await supabase
      .from('daemon_status')
      .select('id, last_seen_at')
      .eq('id', 1)
      .single()

    if (error || !data) {
      setOnline(false)
      setLastSeen(null)
      return
    }

    const row = data as DaemonStatusType
    const seenMs = new Date(row.last_seen_at).getTime()
    const ageSeconds = (Date.now() - seenMs) / 1000
    setOnline(ageSeconds < 60)
    setLastSeen(row.last_seen_at)
  }

  useEffect(() => {
    checkStatus()
    const interval = setInterval(checkStatus, 15_000)
    return () => clearInterval(interval)
  }, [])

  if (online === null) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span className="inline-block w-2 h-2 rounded-full bg-gray-600 animate-pulse" />
        Checking daemon…
      </div>
    )
  }

  if (online) {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-400">
        <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
        Daemon online
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 text-sm text-red-400">
      <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
      <span>
        Daemon offline —{' '}
        <code className="font-mono text-xs bg-gray-800 px-1 py-0.5 rounded">
          python daemon.py
        </code>
      </span>
    </div>
  )
}
