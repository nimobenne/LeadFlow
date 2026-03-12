'use client'

interface ScoreBadgeProps {
  score: number | null
  type: 'fit' | 'confidence' | 'priority'
}

type Tier = { label: string; classes: string }

function getFitTier(score: number): Tier {
  if (score >= 80) return { label: 'A', classes: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700' }
  if (score >= 65) return { label: 'B', classes: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700' }
  if (score >= 50) return { label: 'C', classes: 'bg-orange-900/60 text-orange-300 border border-orange-700' }
  return { label: 'Skip', classes: 'bg-gray-800 text-gray-500 border border-gray-700' }
}

function getConfidenceTier(score: number): Tier {
  if (score >= 75) return { label: 'High', classes: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700' }
  if (score >= 60) return { label: 'OK', classes: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700' }
  if (score >= 45) return { label: 'Review', classes: 'bg-orange-900/60 text-orange-300 border border-orange-700' }
  return { label: 'Skip', classes: 'bg-gray-800 text-gray-500 border border-gray-700' }
}

function getPriorityClasses(score: number): string {
  if (score >= 80) return 'bg-indigo-900/60 text-indigo-300 border border-indigo-700'
  if (score >= 60) return 'bg-blue-900/60 text-blue-300 border border-blue-700'
  if (score >= 40) return 'bg-gray-800 text-gray-300 border border-gray-600'
  return 'bg-gray-900 text-gray-500 border border-gray-700'
}

/**
 * Colored pill badge for fit, confidence, and priority scores.
 * - fit: grades A/B/C/Skip with green/yellow/orange/gray
 * - confidence: labels High/OK/Review/Skip
 * - priority: shows numeric value with color gradient
 */
export default function ScoreBadge({ score, type }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-600 border border-gray-700">
        —
      </span>
    )
  }

  if (type === 'fit') {
    const tier = getFitTier(score)
    return (
      <span className={`inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 rounded ${tier.classes}`}>
        {tier.label}
        <span className="ml-1 text-[10px] opacity-70">{score}</span>
      </span>
    )
  }

  if (type === 'confidence') {
    const tier = getConfidenceTier(score)
    return (
      <span className={`inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 rounded ${tier.classes}`}>
        {tier.label}
        <span className="ml-1 text-[10px] opacity-70">{score}</span>
      </span>
    )
  }

  // priority — numeric with gradient color
  const classes = getPriorityClasses(score)
  return (
    <span className={`inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 rounded ${classes}`}>
      {score}
    </span>
  )
}
