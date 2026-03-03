'use client';

import { FormEvent, useState } from 'react';

export function EmailSignup() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setMessage('');

    const normalized = email.trim().toLowerCase();
    if (!/^\S+@\S+\.\S+$/.test(normalized)) {
      setError('Please enter a valid email address.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalized })
      });
      const data = (await response.json()) as { success?: boolean; message?: string };
      if (!response.ok) throw new Error(data.message || 'Could not save your email.');
      setMessage('Saved! You are on the early access list.');
      setEmail('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <label htmlFor="leadEmail">Get updates and launch discounts</label>
      <div className="row">
        <input
          id="leadEmail"
          className="input"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          required
        />
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? 'Saving...' : 'Join List'}
        </button>
      </div>
      {message ? <p className="status-ok">{message}</p> : null}
      {error ? <p className="status-error">{error}</p> : null}
    </form>
  );
}
