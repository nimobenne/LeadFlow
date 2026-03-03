'use client';

import { FormEvent, useState } from 'react';

export function BuyButton() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    const normalizedEmail = email.trim().toLowerCase();
    const normalizedName = name.trim();

    if (normalizedName.length < 2) {
      setError('Please enter your full name.');
      return;
    }

    if (!/^\S+@\S+\.\S+$/.test(normalizedEmail)) {
      setError('Please enter a valid email to continue.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: normalizedName, email: normalizedEmail })
      });
      const data = (await response.json()) as { checkoutUrl?: string; message?: string };
      if (!response.ok || !data.checkoutUrl) {
        throw new Error(data.message || 'Failed to initialize checkout');
      }
      window.location.href = data.checkoutUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error');
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <label htmlFor="checkoutName">Buy now</label>
      <div className="row">
        <input
          id="checkoutName"
          className="input"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Full name"
          required
        />
        <input
          id="checkoutEmail"
          className="input"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          required
        />
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? 'Redirecting...' : 'Buy PDF'}
        </button>
      </div>
      {error ? <p className="status-error">{error}</p> : null}
    </form>
  );
}
