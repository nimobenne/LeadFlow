import { NextResponse } from 'next/server';
import { getSupabaseServerClient } from '@/lib/supabaseServer';

type LeadPayload = {
  email: string;
  full_name: string;
};

async function insertLead(payload: LeadPayload) {
  const supabase = getSupabaseServerClient();
  const preferredTable = process.env.SUPABASE_LEADS_TABLE?.trim() || 'leads';

  const attemptTables = Array.from(new Set([preferredTable, 'email', 'emails', 'leads']));

  let lastError: string | null = null;

  for (const tableName of attemptTables) {
    const { error } = await supabase.from(tableName).upsert(payload, { onConflict: 'email' });

    if (!error) {
      return { ok: true, tableName };
    }

    lastError = error.message;
  }

  return { ok: false, error: lastError || 'Failed to save lead.' };
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: string; name?: string };
    const email = body.email?.trim().toLowerCase();
    const fullName = body.name?.trim();

    if (!fullName || fullName.length < 2) {
      return NextResponse.json({ success: false, message: 'Valid name is required.' }, { status: 400 });
    }

    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
      return NextResponse.json({ success: false, message: 'Valid email is required.' }, { status: 400 });
    }

    const result = await insertLead({ email, full_name: fullName });

    if (!result.ok) {
      return NextResponse.json({ success: false, message: result.error }, { status: 500 });
    }

    return NextResponse.json({ success: true, table: result.tableName });
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid request.' }, { status: 400 });
  }
}
