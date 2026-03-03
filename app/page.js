'use client';

import { useEffect, useMemo, useState } from 'react';

const bullets = [
  'Daily 15-minute protocol to reset focus and discipline',
  'MentalCore habit stack used by high performers',
  'Confidence scripts to stop overthinking in real time',
  'Printable templates and tracker pages included'
];

function StarRow({ rating }) {
  return (
    <div className="stars" aria-label={`Rated ${rating} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={s <= rating ? 'star filled' : 'star'}>
          ★
        </span>
      ))}
    </div>
  );
}

export default function HomePage() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [formState, setFormState] = useState({ name: '', email: '' });
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    async function loadReviews() {
      try {
        const res = await fetch('/api/reviews');
        const payload = await res.json();
        setReviews(payload.reviews ?? []);
      } finally {
        setLoading(false);
      }
    }

    loadReviews();
  }, []);

  const averageRating = useMemo(() => {
    if (!reviews.length) return 5;
    return (
      reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length
    ).toFixed(1);
  }, [reviews]);

  const onSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatusMessage('');

    try {
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formState)
      });
      const payload = await res.json();

      if (!res.ok) {
        throw new Error(payload.message || 'Something went wrong.');
      }

      setStatusMessage(
        `You're in, ${payload.customer.name}! Check ${payload.customer.email} for next steps.`
      );
      setFormState({ name: '', email: '' });
    } catch (error) {
      setStatusMessage(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main>
      <section className="hero">
        <p className="badge">Official MentalCore YouTube Channel Guide</p>
        <h1>Turn scattered motivation into elite consistency.</h1>
        <p className="subtitle">
          The <strong>MentalCore Mastery PDF</strong> gives you a step-by-step mental system to build discipline,
          stay focused, and perform with confidence every day.
        </p>

        <div className="rating-summary">
          <StarRow rating={Math.round(Number(averageRating))} />
          <p>
            <strong>{averageRating}/5</strong> average from verified readers
          </p>
        </div>

        <div className="hero-cta">
          <p className="price">
            <span>$29</span> one-time payment
          </p>
          <a href="#checkout" className="button-primary">
            Get Instant Access
          </a>
        </div>
      </section>

      <section className="value-grid">
        {bullets.map((bullet) => (
          <article key={bullet}>
            <h3>✔</h3>
            <p>{bullet}</p>
          </article>
        ))}
      </section>

      <section className="reviews">
        <h2>What readers say</h2>
        {loading ? (
          <p>Loading reviews…</p>
        ) : (
          <div className="review-grid">
            {reviews.map((review) => (
              <article key={review.id} className="review-card">
                <StarRow rating={review.rating} />
                <p>“{review.text}”</p>
                <small>
                  {review.name} · {review.role}
                </small>
              </article>
            ))}
          </div>
        )}
      </section>

      <section id="checkout" className="checkout">
        <div>
          <h2>Start building your MentalCore today</h2>
          <p>
            Join the community using this framework to stay disciplined under pressure. Enter your details and we’ll
            send your purchase link instantly.
          </p>
        </div>

        <form onSubmit={onSubmit}>
          <label htmlFor="name">Full name</label>
          <input
            id="name"
            type="text"
            required
            value={formState.name}
            onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Alex Carter"
          />

          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            required
            value={formState.email}
            onChange={(event) => setFormState((prev) => ({ ...prev, email: event.target.value }))}
            placeholder="you@example.com"
          />

          <button className="button-primary" type="submit" disabled={submitting}>
            {submitting ? 'Processing…' : 'Reserve My Copy'}
          </button>
          {statusMessage && <p className="status">{statusMessage}</p>}
        </form>
      </section>
    </main>
  );
}
