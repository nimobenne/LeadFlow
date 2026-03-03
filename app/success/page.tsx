import Link from 'next/link';
import { getSupabaseServerClient } from '@/lib/supabaseServer';

type SuccessProps = {
  searchParams: {
    session_id?: string;
  };
};

export default async function SuccessPage({ searchParams }: SuccessProps) {
  const sessionId = searchParams.session_id?.trim();

  if (!sessionId) {
    return (
      <main className="container">
        <section className="card section">
          <h1>Missing checkout session</h1>
          <p>Please use the link returned by Stripe checkout.</p>
          <Link href="/">Go back</Link>
        </section>
      </main>
    );
  }

  const supabase = getSupabaseServerClient();

  const { data: order } = await supabase
    .from('orders')
    .select('status')
    .eq('stripe_session_id', sessionId)
    .maybeSingle();

  if (!order || order.status !== 'paid') {
    return (
      <main className="container">
        <section className="card section">
          <h1>Payment processing</h1>
          <p>
            We are still confirming your payment. Refresh in a few seconds. If this persists, contact support with your
            email receipt.
          </p>
        </section>
      </main>
    );
  }

  const bucket = process.env.SUPABASE_PDF_BUCKET || 'products';
  const filePath = process.env.SUPABASE_PDF_PATH || 'mentalcore-mastery.pdf';

  const { data: signedData, error } = await supabase.storage.from(bucket).createSignedUrl(filePath, 60 * 10);

  if (error || !signedData?.signedUrl) {
    return (
      <main className="container">
        <section className="card section">
          <h1>Delivery unavailable</h1>
          <p>We could not generate your secure download link right now. Please contact support.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="container">
      <section className="card section">
        <h1>Payment confirmed</h1>
        <p>Your secure download link is ready and will expire automatically.</p>
        <a className="btn btn-primary" href={signedData.signedUrl} target="_blank" rel="noreferrer">
          Download MentalCore PDF
        </a>
      </section>
    </main>
  );
}
