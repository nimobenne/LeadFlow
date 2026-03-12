import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const GITHUB_TOKEN = process.env.GITHUB_TOKEN!
const GITHUB_REPO = process.env.GITHUB_REPO ?? 'nimobenne/LeadFlow'
const WORKFLOW_FILE = 'pipeline.yml'
const BRANCH = 'main'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { cities, lead_limit, force_refresh } = body as {
      cities: string[]
      lead_limit: number
      force_refresh: boolean
    }

    if (!cities || cities.length === 0) {
      return NextResponse.json({ error: 'cities is required' }, { status: 400 })
    }

    if (!GITHUB_TOKEN) {
      return NextResponse.json({ error: 'GITHUB_TOKEN not configured' }, { status: 500 })
    }

    // 1. Create the job record in Supabase first so we have an ID
    const { data: job, error: jobError } = await supabase
      .from('jobs')
      .insert({
        status: 'pending',
        cities,
        lead_limit: lead_limit ?? 100,
        force_refresh: force_refresh ?? false,
      })
      .select('id')
      .single()

    if (jobError || !job) {
      console.error('Failed to create job:', jobError)
      return NextResponse.json({ error: 'Failed to create job record' }, { status: 500 })
    }

    const jobId = job.id as string

    // 2. Trigger GitHub Actions workflow with the job ID
    const ghResponse = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ref: BRANCH,
          inputs: {
            cities: cities.join(','),
            lead_limit: String(lead_limit ?? 100),
            force_refresh: String(force_refresh ?? false),
            job_id: jobId,
          },
        }),
      }
    )

    if (!ghResponse.ok) {
      const ghError = await ghResponse.text()
      console.error('GitHub API error:', ghResponse.status, ghError)

      // Roll back the job record
      await supabase.from('jobs').delete().eq('id', jobId)

      return NextResponse.json(
        { error: `GitHub Actions trigger failed: ${ghResponse.status}` },
        { status: 502 }
      )
    }

    return NextResponse.json({ job_id: jobId })
  } catch (err) {
    console.error('Trigger error:', err)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
