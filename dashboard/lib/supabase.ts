import { createClient } from '@supabase/supabase-js'

/**
 * Singleton Supabase client using the anon key.
 * Safe for use in both client and server components.
 * RLS is disabled for v1, so all reads/writes are unrestricted.
 */
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
