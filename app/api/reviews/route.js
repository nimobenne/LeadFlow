import { NextResponse } from 'next/server';

const reviews = [
  {
    id: 1,
    name: 'Jordan M.',
    role: 'University Student',
    rating: 5,
    text: 'I stopped procrastinating in week one. The checklist made my routine automatic.'
  },
  {
    id: 2,
    name: 'Rashida K.',
    role: 'Founder',
    rating: 5,
    text: 'Clean, practical, and zero fluff. I now use the confidence script before every meeting.'
  },
  {
    id: 3,
    name: 'Evan T.',
    role: 'Gym Coach',
    rating: 4,
    text: 'The focus reset alone is worth the price. Clients noticed my energy and consistency.'
  }
];

export async function GET() {
  return NextResponse.json({ reviews });
}
