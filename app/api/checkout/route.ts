import { NextResponse } from 'next/server';
import { getStripeServerClient } from '@/lib/stripe';
import { getSupabaseServerClient } from '@/lib/supabaseServer';

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { email?: string };
    const email = body.email?.trim().toLowerCase();

    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
      return NextResponse.json({ message: 'Valid email is required.' }, { status: 400 });
    }

    const stripe = getStripeServerClient();
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
    const priceId = process.env.STRIPE_PRICE_ID;

    if (!siteUrl || !priceId) {
      return NextResponse.json({ message: 'Server is missing payment configuration.' }, { status: 500 });
    }

    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      customer_email: email,
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: `${siteUrl}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${siteUrl}/cancel`,
      metadata: { email }
    });

    const supabase = getSupabaseServerClient();
    const { error } = await supabase.from('orders').insert({
      email,
      stripe_session_id: session.id,
      status: 'pending'
    });

    if (error) {
      return NextResponse.json({ message: 'Could not create order record.' }, { status: 500 });
    }

    return NextResponse.json({ checkoutUrl: session.url });
  } catch {
    return NextResponse.json({ message: 'Failed to create checkout session.' }, { status: 500 });
  }
}
