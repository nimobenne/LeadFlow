import { BuyButton } from '@/components/BuyButton';
import { EmailSignup } from '@/components/EmailSignup';

const reviews = [
  { name: 'Daria', text: 'Simple system. Massive consistency gains.', stars: 5 },
  { name: 'Alex', text: 'Best mental reset routine I have used.', stars: 5 },
  { name: 'Mina', text: 'No fluff. Actionable and effective.', stars: 4 }
];

export default function HomePage() {
  return (
    <main className="container">
      <section className="card hero">
        <span>Official MentalCore YouTube Product</span>
        <h1>MentalCore Mastery PDF</h1>
        <p>
          A practical mental performance system to improve focus, reduce overthinking, and build disciplined daily
          action.
        </p>
        <div className="row">
          <strong>$29 one-time</strong>
          <span>Instant digital delivery after payment</span>
        </div>
        <EmailSignup />
        <BuyButton />
      </section>

      <section className="card section">
        <h2>Why customers buy</h2>
        <div className="grid">
          <div className="card section">Daily clarity routines</div>
          <div className="card section">Confidence and emotional regulation frameworks</div>
          <div className="card section">Action templates and habit trackers</div>
        </div>
      </section>

      <section className="card section">
        <h2>Reviews</h2>
        <div className="grid">
          {reviews.map((review) => (
            <article key={review.name} className="card section">
              <div className="star">{'★'.repeat(review.stars)}</div>
              <p>"{review.text}"</p>
              <strong>{review.name}</strong>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
