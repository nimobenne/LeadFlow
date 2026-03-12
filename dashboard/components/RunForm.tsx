'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { X, ChevronDown, Search } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { UK_CITIES } from '@/lib/uk-cities'

interface RunFormProps {
  /** Called with the new job ID once the run is inserted into Supabase. */
  onRunStarted: (jobId: string) => void
  /** Whether the daemon is currently online. Disables submit when false. */
  daemonOnline: boolean | null
}

/**
 * Form to configure and trigger a new pipeline run.
 * Inserts a job record into the `jobs` table on submit.
 */
export default function RunForm({ onRunStarted, daemonOnline }: RunFormProps) {
  const router = useRouter()

  const [selectedCities, setSelectedCities] = useState<string[]>([])
  const [citySearch, setCitySearch] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [leadLimit, setLeadLimit] = useState(100)
  const [forceRefresh, setForceRefresh] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const filteredCities = UK_CITIES.filter(
    (c) =>
      c.toLowerCase().includes(citySearch.toLowerCase()) &&
      !selectedCities.includes(c)
  )

  function toggleCity(city: string) {
    setSelectedCities((prev) =>
      prev.includes(city) ? prev.filter((c) => c !== city) : [...prev, city]
    )
  }

  function removeCity(city: string) {
    setSelectedCities((prev) => prev.filter((c) => c !== city))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedCities.length === 0) return
    setSubmitting(true)
    setError(null)

    const { data, error: insertError } = await supabase
      .from('jobs')
      .insert({
        status: 'pending',
        cities: selectedCities,
        lead_limit: leadLimit,
        force_refresh: forceRefresh,
      })
      .select('id')
      .single()

    if (insertError || !data) {
      setError(insertError?.message ?? 'Failed to create job.')
      setSubmitting(false)
      return
    }

    onRunStarted(data.id as string)
    setSubmitting(false)
  }

  const canSubmit = daemonOnline === true && selectedCities.length > 0 && !submitting

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* City multi-select */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-300">
          Cities <span className="text-gray-500 font-normal">(select one or more)</span>
        </label>

        {/* Selected tags */}
        {selectedCities.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {selectedCities.map((city) => (
              <span
                key={city}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-indigo-900/70 border border-indigo-600 text-indigo-200 text-sm"
              >
                {city}
                <button
                  type="button"
                  onClick={() => removeCity(city)}
                  className="text-indigo-400 hover:text-indigo-200 transition-colors"
                  aria-label={`Remove ${city}`}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Dropdown trigger */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen((o) => !o)}
            className="w-full flex items-center justify-between px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-left text-sm text-gray-300 hover:border-indigo-600 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-600"
          >
            <span className={selectedCities.length === 0 ? 'text-gray-500' : ''}>
              {selectedCities.length === 0
                ? 'Select cities…'
                : `${selectedCities.length} ${selectedCities.length === 1 ? 'city' : 'cities'} selected`}
            </span>
            <ChevronDown
              size={16}
              className={`text-gray-500 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {dropdownOpen && (
            <div className="absolute z-50 w-full mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
              {/* Search */}
              <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-700">
                <Search size={14} className="text-gray-500 shrink-0" />
                <input
                  type="text"
                  value={citySearch}
                  onChange={(e) => setCitySearch(e.target.value)}
                  placeholder="Search cities…"
                  className="w-full bg-transparent text-sm text-gray-200 placeholder-gray-600 focus:outline-none"
                  autoFocus
                />
              </div>
              {/* Options */}
              <div className="max-h-56 overflow-y-auto">
                {filteredCities.length === 0 ? (
                  <p className="px-3 py-2 text-sm text-gray-600">No matching cities</p>
                ) : (
                  filteredCities.map((city) => (
                    <button
                      key={city}
                      type="button"
                      onClick={() => {
                        toggleCity(city)
                        setCitySearch('')
                      }}
                      className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-indigo-900/40 hover:text-indigo-200 transition-colors"
                    >
                      {city}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Lead limit slider */}
      <div className="space-y-2">
        <label className="flex items-center justify-between text-sm font-medium text-gray-300">
          Lead limit
          <span className="font-mono text-indigo-400 text-base">{leadLimit}</span>
        </label>
        <input
          type="range"
          min={50}
          max={200}
          step={10}
          value={leadLimit}
          onChange={(e) => setLeadLimit(Number(e.target.value))}
          className="w-full h-2 rounded-lg appearance-none cursor-pointer
            bg-gray-700
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-indigo-500
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:shadow-[0_0_0_2px_#312e81]
            [&::-moz-range-thumb]:w-4
            [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:rounded-full
            [&::-moz-range-thumb]:bg-indigo-500
            [&::-moz-range-thumb]:border-0"
          aria-valuemin={50}
          aria-valuemax={200}
          aria-valuenow={leadLimit}
        />
        <div className="flex justify-between text-xs text-gray-600">
          <span>50</span>
          <span>200</span>
        </div>
      </div>

      {/* Force refresh checkbox */}
      <label className="flex items-start gap-3 cursor-pointer group">
        <div className="relative mt-0.5">
          <input
            type="checkbox"
            checked={forceRefresh}
            onChange={(e) => setForceRefresh(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-4 h-4 rounded border border-gray-600 bg-gray-800 peer-checked:bg-indigo-600 peer-checked:border-indigo-600 transition-colors group-hover:border-gray-500" />
          {forceRefresh && (
            <svg
              className="absolute inset-0 w-4 h-4 text-white pointer-events-none"
              viewBox="0 0 16 16"
              fill="none"
            >
              <path
                d="M3 8l3.5 3.5 6.5-7"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
        <div>
          <span className="text-sm font-medium text-gray-300">Re-scrape existing leads</span>
          <p className="text-xs text-gray-600 mt-0.5">
            Force the pipeline to re-fetch data for businesses already in the database
          </p>
        </div>
      </label>

      {/* Error */}
      {error && (
        <p className="text-sm text-red-400 bg-red-950/50 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {/* Daemon offline warning */}
      {daemonOnline === false && (
        <p className="text-sm text-amber-400 bg-amber-950/50 border border-amber-800 rounded-lg px-3 py-2">
          The daemon must be running before you can start a pipeline run.
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full py-2.5 px-4 rounded-lg text-sm font-semibold transition-all
          bg-indigo-600 text-white
          hover:bg-indigo-500
          disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-indigo-600
          focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-950"
      >
        {submitting ? 'Starting…' : 'Start Run'}
      </button>
    </form>
  )
}
