import { NextResponse } from 'next/server';
import Stripe from 'stripe';
import { getStripeServerClient } from '@/lib/stripe';
import { getSupabaseServerClient } from '@/lib/supabaseServer';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const stripe = getStripeServerClient();
  const signature = request.headers.get('stripe-signature');
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

  if (!signature || !webhookSecret) {
    return NextResponse.json({ message: 'Missing Stripe signature or webhook secret.' }, { status: 400 });
  }

  const payload = await request.text();
  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(payload, signature, webhookSecret);
  } catch {
    return NextResponse.json({ message: 'Invalid webhook signature.' }, { status: 400 });
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object as Stripe.Checkout.Session;

    const supabase = getSupabaseServerClient();
    await supabase
      .from('orders')
      .update({
        status: 'paid',
        stripe_payment_intent_id: typeof session.payment_intent === 'string' ? session.payment_intent : null
      })
      .eq('stripe_session_id', session.id);
  }

  return NextResponse.json({ received: true }, { status: 200 });
}
