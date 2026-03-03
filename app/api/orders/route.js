import { NextResponse } from 'next/server';

export async function POST(request) {
  const body = await request.json();
  const name = (body?.name || '').trim();
  const email = (body?.email || '').trim();

  if (!name || !email || !email.includes('@')) {
    return NextResponse.json(
      { message: 'Please enter a valid name and email to continue.' },
      { status: 400 }
    );
  }

  return NextResponse.json({
    message: 'Order intent captured',
    customer: { name, email }
  });
}
